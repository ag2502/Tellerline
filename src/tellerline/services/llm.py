"""The agent's turn as a Pipecat LLM service: route, generate, validate, act, speak.

Subclasses Pipecat's OpenAI-compatible service so interruptions, metrics and tracing work as
for any LLM, but replaces how a response is produced. The service talks to the local mlx-lm
server; it never uses tool calling.
"""

from datetime import date
from typing import Any, Protocol

from loguru import logger
from pipecat.frames.frames import EndTaskFrame
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.utils.tracing.service_decorators import traced_llm

from tellerline.actions import Action, ReplySplitter, clarifying_question, parse_action
from tellerline.banking.responses import respond
from tellerline.brain import Plan
from tellerline.llm_server import MAX_TOKENS, base_url

DIDNT_CATCH = "Sorry, I didn't quite catch that. Could you say it again?"
CANT_DO_NOW = "Sorry, I can't do that right now. I'll transfer you to a colleague."
NOT_VERIFIED_TRANSFER = (
    "I'm sorry, I still can't verify your details, so I'll transfer you to a colleague."
)
ENDS_CALL = frozenset({"end_call", "transfer_to_human"})


class Brain(Protocol):
    def plan(self, text: str) -> Plan: ...
    def record(self, text: str, plan: Plan, action: Action | None, spoken: str) -> None: ...


class Bank(Protocol):
    async def run(self, action: Action) -> dict[str, Any]: ...


def _text(content) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return " ".join(p.get("text", "") for p in content if isinstance(p, dict)).strip()
    return ""


def last_user_text(context: LLMContext) -> str:
    """Everything the caller said since the agent last spoke, as one message.

    A caller who pauses mid-sentence ("My customer number is 45127890 ... and my date of birth
    is ...") produces several user messages when the pause looks like the end of their turn.
    The answer must consider all of them, not just the last fragment.
    """
    parts: list[str] = []
    for message in reversed(context.get_messages()):
        role = message.get("role")
        if role == "assistant":
            break
        if role == "user" and (text := _text(message.get("content"))):
            parts.append(text)
    return " ".join(reversed(parts))


class TellerlineLLMService(OpenAILLMService):
    def __init__(
        self,
        *,
        brain: Brain,
        bank: Bank,
        model: str,
        today: date | None = None,
        llm_url: str | None = None,
        max_failed_verifications: int = 3,
        **kwargs,
    ):
        super().__init__(
            api_key="not-needed",
            base_url=llm_url or base_url(),
            settings=OpenAILLMService.Settings(model=model, temperature=0.0, max_tokens=MAX_TOKENS),
            **kwargs,
        )
        self._brain = brain
        self._bank = bank
        self._model = model
        self._today = today
        self._max_failed_verifications = max_failed_verifications
        self._failed_verifications = 0

    @traced_llm
    async def _process_context(self, context: LLMContext):
        text = last_user_text(context)
        if not text:
            return
        plan = self._brain.plan(text)
        logger.debug(f"Turn routed to '{plan.step}' ({plan.route_reason or 'single prompt'})")

        splitter = ReplySplitter()
        await self.start_ttfb_metrics()
        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=plan.messages,
            stream=True,
            temperature=0.0,
            max_tokens=MAX_TOKENS,
            stop=["\n"],  # an action is one line; replies are one or two sentences
        )
        first = True
        try:
            async for chunk in stream:
                piece = chunk.choices[0].delta.content if chunk.choices else None
                if not piece:
                    continue
                if first:
                    await self.stop_ttfb_metrics()
                    first = False
                if speech := splitter.feed(piece):
                    await self._push_llm_text(speech)
        finally:
            await stream.close()
        if speech := splitter.finish():
            await self._push_llm_text(speech)

        action = None
        spoken = splitter.text.strip()
        if splitter.is_action:
            spoken, action = await self._act(plan, splitter.text)
            await self._push_llm_text(spoken)
        self._brain.record(text, plan, action, spoken)

        if action and action.tool in ENDS_CALL:
            # Ends after what's already queued has been spoken.
            await self.push_frame(EndTaskFrame(), FrameDirection.UPSTREAM)

    async def _act(self, plan: Plan, line: str) -> tuple[str, Action | None]:
        """Validate and run an ACTION line; return what to say and the action that happened."""
        action = parse_action(line, plan.allowed)
        if action is None:
            logger.warning(f"Unusable action line: {line!r}")
            return DIDNT_CATCH, None
        if not action.complete:
            return clarifying_question(action), None
        try:
            result = await self._bank.run(action)
        except Exception as error:  # the caller hears an apology, not a stack trace
            logger.exception(f"Bank call failed for {action.tool}: {error}")
            return CANT_DO_NOW, Action("transfer_to_human", {})

        today = self._today or date.today()
        if action.tool == "verify_identity" and not result.get("verified"):
            self._failed_verifications += 1
            if self._failed_verifications >= self._max_failed_verifications:
                await self._bank.run(Action("transfer_to_human", {"reason": "verification failed"}))
                return NOT_VERIFIED_TRANSFER, Action("transfer_to_human", {})
            return respond(action.tool, action.arguments, result, today), None
        return respond(action.tool, action.arguments, result, today), action
