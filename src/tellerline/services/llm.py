"""The agent's turn as a Pipecat LLM service: route, generate, validate, act, speak.

Subclasses Pipecat's OpenAI-compatible service so interruptions, metrics and tracing work as
for any LLM, but replaces how a response is produced. The service talks to the local mlx-lm
server; it never uses tool calling.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol

from loguru import logger
from opentelemetry import trace
from pipecat.frames.frames import (
    BotStoppedSpeakingFrame,
    EndWorkerFrame,
    Frame,
    LLMContextAssistantTurnFrame,
)
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.frame_processor import FrameDirection
from pipecat.processors.frameworks.rtvi.frames import RTVIServerMessageFrame
from pipecat.services.openai.llm import OpenAILLMService
from pipecat.utils.tracing.service_decorators import traced_llm

from tellerline.actions import Action, ReplySplitter
from tellerline.banking.responses import respond
from tellerline.brain import DIDNT_CATCH, VERIFY_FIRST, Outcome, Plan
from tellerline.config import FLOOR_HOLD_MAX_S, IDENTITY_HOLD_S
from tellerline.llm_server import MAX_TOKENS, base_url

__all__ = ["DIDNT_CATCH", "VERIFY_FIRST", "TellerlineLLMService"]

CANT_DO_NOW = "Sorry, I can't do that right now. I'll transfer you to a colleague."
NOT_VERIFIED_TRANSFER = (
    "I'm sorry, I still can't verify your details, so I'll transfer you to a colleague."
)
ENDS_CALL = frozenset({"end_call", "transfer_to_human"})
# A call that ends (goodbye, or a transfer) waits for the agent to finish its last words: ending
# straight away disconnects the WebRTC peer before the goodbye has left the Mac. A short grace
# lets the last audio drain, and the call ends anyway if speech never finishes.
END_GRACE_S = 0.5
END_TIMEOUT_S = 15.0


class Brain(Protocol):
    def plan(self, text: str) -> Plan: ...
    def interpret(self, plan: Plan, answer: str) -> Outcome: ...
    def record(self, text: str, plan: Plan, action: Action | None, spoken: str) -> None: ...
    def withdraw(self) -> None: ...


class Bank(Protocol):
    async def run(self, action: Action) -> dict[str, Any]: ...


class Timeline(Protocol):
    def add_turn(self, record: dict[str, Any]) -> dict[str, Any]: ...
    def withdraw_turn(self, turn: int) -> None: ...


@dataclass
class TurnResult:
    """What an ACTION line led to: the words spoken, the action that ran, and how."""

    spoken: str
    action: Action | None = None
    instead: str | None = None  # why the line wasn't run as written
    bank: dict[str, Any] = field(default_factory=dict)


@dataclass
class Unheard:
    """A turn whose reply the caller hasn't heard a sentence of yet."""

    result: TurnResult
    turn: int | None = None  # its number on the call's timeline


def _ms(seconds: float) -> float:
    return round(seconds * 1000, 1)


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
        timeline: Timeline | None = None,
        identity_hold_s: float = IDENTITY_HOLD_S,
        end_grace_s: float = END_GRACE_S,
        end_timeout_s: float = END_TIMEOUT_S,
        whole_turn: Callable[[str], Awaitable[str | None]] | None = None,
        hears_caller: Callable[[], bool] | None = None,
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
        # The caller's turn transcribed in one pass, when it came in pieces (Parakeet's
        # turn_transcript); None when the turn was a single segment.
        self._whole_turn = whole_turn
        # Whether the VAD can hear the caller right now (the floor rules); None to never wait.
        self._hears_caller = hears_caller
        # The last turn, until the caller has heard a sentence of its reply.
        self._unheard: Unheard | None = None
        # What the last turn did, when its reply was withdrawn unheard: the same action asked for
        # again isn't run twice.
        self._done: TurnResult | None = None
        self._model = model
        self._today = today
        self._max_failed_verifications = max_failed_verifications
        self._failed_verifications = 0
        self._timeline = timeline
        self._identity_hold_s = identity_hold_s
        self._end_grace_s = end_grace_s
        self._end_timeout_s = end_timeout_s
        self._ending = False  # the agent has ended the call; it stays ended
        self._hung_up = False
        self._end_timer: asyncio.Task | None = None

    @traced_llm
    async def _process_context(self, context: LLMContext):
        text = last_user_text(context)
        if not text:
            return
        if self._ending:
            # The call is over: a "Thanks, bye" whose turn began before the goodbye gets no
            # second goodbye.
            logger.debug(f"Call ended; not answering {text!r}")
            return
        await self._withdraw_unheard()
        if self._whole_turn is not None and (whole := await self._whole_turn(text)):
            # The turn came in pieces (the caller paused); heard whole, words split across a
            # pause aren't lost or doubled.
            if whole != text:
                logger.debug(f"Turn heard whole: [{whole}] (in pieces: [{text}])")
            text = whole
        plan = self._brain.plan(text)
        logger.debug(f"Turn routed to '{plan.step}' ({plan.route_reason or 'single prompt'})")
        span = trace.get_current_span()
        span.set_attribute("tellerline.route.step", plan.step)
        span.set_attribute("tellerline.route.reason", plan.route_reason)
        span.set_attribute("tellerline.route.seconds", plan.route_s)
        if plan.intent is not None:
            span.set_attribute("tellerline.intent", plan.intent)
            span.set_attribute("tellerline.intent.score", float(plan.intent_score or 0.0))

        splitter = ReplySplitter()
        await self.start_ttfb_metrics()
        asked = time.perf_counter()
        # Half the identity details: hold the reply briefly. A caller who carries on starts a new
        # turn, which cancels this one before anything is said over them.
        hold_until = asked + self._identity_hold_s if plan.hold else 0.0

        async def say(text: str) -> None:
            nonlocal hold_until
            if hold_until and (wait := hold_until - time.perf_counter()) > 0:
                await asyncio.sleep(wait)
            hold_until = 0.0
            await self._push_llm_text(text)

        first_token_s = None
        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=plan.messages,
            stream=True,
            temperature=0.0,
            max_tokens=MAX_TOKENS,
            stop=["\n"],  # an action is one line; replies are one or two sentences
        )
        try:
            async for chunk in stream:
                piece = chunk.choices[0].delta.content if chunk.choices else None
                if not piece:
                    continue
                if first_token_s is None:
                    first_token_s = time.perf_counter() - asked
                    await self.stop_ttfb_metrics()
                if speech := splitter.feed(piece):
                    await say(speech)
        finally:
            await stream.close()
        model_s = time.perf_counter() - asked
        if speech := splitter.finish():
            await say(speech)

        result = TurnResult(splitter.text.strip())
        if splitter.is_action:
            result = await self._act(plan, splitter.text)
            await say(result.spoken)
        action, spoken = result.action, result.spoken
        self._brain.record(text, plan, action, spoken)
        self._done = None
        span.set_attribute("tellerline.model_output", splitter.text.strip())
        span.set_attribute("tellerline.action", action.tool if action else "")
        span.set_attribute("tellerline.spoken", spoken)
        turn = await self._report(plan, text, splitter.text.strip(), first_token_s, model_s, result)
        self._unheard = Unheard(result, turn)

        if action and action.tool in ENDS_CALL:
            self._ending = True
            self._end_timer = self.create_task(self._end_after(self._end_timeout_s))

    @property
    def ending(self) -> bool:
        """The agent has ended the call (a goodbye or a transfer) and is saying its last words."""
        return self._ending

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, LLMContextAssistantTurnFrame) and frame.text.strip():
            # A sentence of the reply was said (the assistant aggregator keeps only what was).
            self._unheard = None
        if isinstance(frame, BotStoppedSpeakingFrame) and self._ending and not self._hung_up:
            # The goodbye (or transfer message) has been spoken; let it drain, then hang up.
            if self._end_timer is not None:
                await self.cancel_task(self._end_timer)
            self._end_timer = self.create_task(self._end_after(self._end_grace_s))

    async def _end_after(self, seconds: float) -> None:
        await asyncio.sleep(seconds)
        # The worker finishes what's already in the pipeline before it ends, so `ending` stays
        # set: a "bye" heard in that time must not start another turn.
        if self._ending and not self._hung_up:
            self._hung_up = True
            await self.push_frame(EndWorkerFrame(), FrameDirection.UPSTREAM)

    async def _withdraw_unheard(self) -> None:
        """Forget the last turn if the caller never heard a sentence of its reply.

        They carried on after a pause and took the turn back (the floor rules), so this turn
        holds what they said before as well (``last_user_text``) and is answered afresh, as if
        the agent had waited. What the withdrawn turn did stays done: the bank isn't asked to do
        it twice (``_done``).
        """
        unheard, self._unheard = self._unheard, None
        if unheard is None:
            return
        self._brain.withdraw()
        self._done = unheard.result if unheard.result.action else None
        logger.debug(
            f"Withdrew turn {unheard.turn}: the caller carried on before hearing its reply"
        )
        if self._timeline is not None and unheard.turn is not None:
            self._timeline.withdraw_turn(unheard.turn)
        if unheard.turn is not None:
            message = {"type": "tellerline-withdrawn", "turn": unheard.turn}
            await self.push_frame(RTVIServerMessageFrame(data=message))

    async def _floor(self) -> None:
        """Wait while the caller can be heard, at most FLOOR_HOLD_MAX_S.

        A caller who carried on after a pause may change what should be done ("Freeze my card,
        ... actually, no"). If the VAD confirms they're talking, their turn starts and cancels
        this one before the bank is asked.
        """
        if self._hears_caller is None:
            return
        started = time.monotonic()
        while self._hears_caller() and time.monotonic() - started < FLOOR_HOLD_MAX_S:
            await asyncio.sleep(0.01)

    async def _report(
        self,
        plan: Plan,
        heard: str,
        output: str,
        first_token_s: float | None,
        model_s: float,
        result: TurnResult,
    ) -> int | None:
        """Add the turn to the call's timeline and send it to the call page's glass-box view;
        the turn's number on the timeline."""
        record = {
            "heard": plan.heard or heard,
            "understood": plan.text or heard,
            "route": {
                "skill": plan.step,
                "reason": plan.route_reason,
                "intent": plan.intent,
                "score": None if plan.intent_score is None else round(plan.intent_score, 3),
                "ms": _ms(plan.route_s),
            },
            "model": {
                "output": output,
                "first_token_ms": None if first_token_s is None else _ms(first_token_s),
                "ms": _ms(model_s),
            },
            "action": (
                {"tool": result.action.tool, "arguments": result.action.arguments}
                if result.action
                else None
            ),
            "instead": result.instead,
            "bank": result.bank or None,
            "spoken": result.spoken,
        }
        if self._timeline is not None:
            record = self._timeline.add_turn(record)
        await self.push_frame(RTVIServerMessageFrame(data={"type": "tellerline-turn", **record}))
        return record.get("turn")

    async def _act(self, plan: Plan, line: str) -> TurnResult:
        """Validate and run an ACTION line: what to say, the action that happened, and how."""
        outcome = self._brain.interpret(plan, line)
        if outcome.action is None:
            logger.info(f"Not running {line!r}: {outcome.reason}")
            return TurnResult(outcome.say or DIDNT_CATCH, instead=outcome.reason)
        action = outcome.action
        if self._done is not None and self._done.action == action:
            # Done already, for a reply the caller never heard.
            return self._done
        await self._floor()
        started = time.perf_counter()
        try:
            result = await self._bank.run(action)
        except Exception as error:  # the caller hears an apology, not a stack trace
            logger.exception(f"Bank call failed for {action.tool}: {error}")
            bank = {"ms": _ms(time.perf_counter() - started), "outcome": "failed"}
            return TurnResult(CANT_DO_NOW, Action("transfer_to_human", {}), bank=bank)
        bank = {
            "ms": _ms(time.perf_counter() - started),
            "outcome": result.get("error") or result.get("status") or "ok",
        }

        today = self._today or date.today()
        if action.tool == "verify_identity" and not result.get("verified"):
            bank["outcome"] = "not verified"
            self._failed_verifications += 1
            if self._failed_verifications >= self._max_failed_verifications:
                await self._bank.run(Action("transfer_to_human", {"reason": "verification failed"}))
                return TurnResult(NOT_VERIFIED_TRANSFER, Action("transfer_to_human", {}), bank=bank)
            return TurnResult(respond(action.tool, action.arguments, result, today), bank=bank)
        if action.tool == "verify_identity":
            bank["outcome"] = "verified"
        spoken = respond(action.tool, action.arguments, result, today)
        return TurnResult(spoken, action, bank=bank)
