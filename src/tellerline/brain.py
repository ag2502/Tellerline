"""The agent's decision step, independent of audio.

For each caller turn a brain makes the caller's words exact (``tellerline.understanding``),
builds the LLM messages and says which actions the model may take; ``interpret`` then turns the
model's answer into what happens; after the turn it records what the caller heard and updates the
call's state. The voice pipeline and the benchmarks both drive these classes.

- ``SinglePromptBrain``: one prompt for the whole call, switching from the identify step to the
  assist step once the caller is verified.
- ``RouterBrain``: a CPU intent classifier and session rules pick one focused skill prompt per
  turn (``tellerline.router``).
"""

import re
from dataclasses import dataclass
from datetime import date
from time import perf_counter
from typing import Protocol

from tellerline.actions import ACTIONS, NODE_ACTIONS, Action, clarifying_question, parse_action
from tellerline.prompts import build_system_prompt
from tellerline.router.classifier import Prediction
from tellerline.router.session import FALLBACK_SKILL, Session
from tellerline.router.skills import SKILL_ACTIONS, build_skill_prompt
from tellerline.understanding import understand

GREETING = (
    "Hello, you're through to Tellerline Bank. I'm an AI assistant. How can I help you today?"
)
DIDNT_CATCH = "Sorry, I didn't quite catch that. Could you say it again?"
VERIFY_FIRST = (
    "I can help with that once I've checked it's you. Could you tell me your eight-digit "
    "customer number and your date of birth, please?"
)
ANYTHING_ELSE = "No problem. Is there anything else I can help with?"
# Ending the call can't be undone, so the caller has to have said goodbye or that they're done;
# a model that hears "No, I'm sure it'll turn up" as a goodbye would hang up on them.
_GOODBYE = re.compile(
    r"\b(?:good)?bye\b|\bcheers\b|\bthat'?s (?:all|everything|it|me)\b"
    r"|\bthat (?:is|was|will be|'ll be) (?:all|everything)\b"
    r"|\bnothing else\b|\ball (?:done|sorted)\b"
    r"|\bi'?m (?:all )?(?:done|finished|sorted|grand now)\b"
    r"|\bhave a (?:good|nice|great) (?:day|one|evening)\b"
    r"|\btalk (?:to you )?soon\b|\bsee you\b",
    re.I,
)
# Values the bank acts on that only the caller can supply. The model must not invent them, copy
# them from an example or work them out from another number (the last four digits of a customer
# number are not a card), so each must appear in something the caller actually said.
GROUNDED = ("card_last_four", "customer_number")


class Classifier(Protocol):
    def predict(self, text: str) -> Prediction: ...


@dataclass(frozen=True)
class Plan:
    messages: list[dict]
    allowed: tuple[str, ...]
    step: str
    route_s: float = 0.0
    route_reason: str = ""
    intent: str | None = None
    intent_score: float | None = None
    heard: str = ""  # what speech recognition wrote
    text: str = ""  # the same words with digits, amounts and dates made exact
    # The caller has probably paused mid-sentence (``mid_sentence``): the reply waits a moment.
    hold: bool = False


@dataclass(frozen=True)
class Outcome:
    """What the model's answer leads to: an action for the bank, or something to say instead."""

    action: Action | None = None
    say: str | None = None
    reason: str = ""  # why the answer wasn't run as written, for logs and traces


_CUSTOMER_NUMBER = re.compile(r"(?<!\d)\d{8}(?!\d)")
_DATE = re.compile(r"\(\d{4}-\d{2}-\d{2}\)")


# A label with its value still to come: "My customer number...", "the card ends in...".
_DANGLING_LABEL = re.compile(
    r"\b(?:customer number|account number|date of birth|birthday|born(?: on)?"
    r"|card (?:number|ending|ends)(?: in)?|ending(?: in)?|ends(?: in)?|number is)[\s.,]*$",
    re.I,
)


def half_identified(text: str) -> bool:
    """The turn gives a customer number or a date, but not both."""
    return bool(_CUSTOMER_NUMBER.search(text)) != bool(_DATE.search(text))


def mid_sentence(text: str, verified: bool) -> bool:
    """The caller has probably paused mid-sentence: the reply should wait a moment.

    Either an unverified caller has given half their details, or a turn ends on a label whose
    value is still to come (questions excepted: "What's my account number?").
    """
    if not verified and half_identified(text):
        return True
    return not text.rstrip().endswith("?") and bool(_DANGLING_LABEL.search(text))


def opening_history() -> list[dict]:
    """The call so far when the caller first speaks: they said hello and heard the greeting."""
    return [{"role": "user", "content": "Hello?"}, {"role": "assistant", "content": GREETING}]


class SinglePromptBrain:
    name = "single"

    def __init__(self, today: date, verified: bool = False, history: list[dict] | None = None):
        self.today = today
        self.verified = verified
        self.history = list(history if history is not None else opening_history())

    def plan(self, heard: str) -> Plan:
        text = understand(heard, self.today)
        step = "assist" if self.verified else "identify"
        system = build_system_prompt(self.today, step, "actions")
        hold = mid_sentence(text, self.verified)
        return Plan(
            self._messages(system, text),
            NODE_ACTIONS[step],
            step,
            heard=heard,
            text=text,
            hold=hold,
        )

    def interpret(self, plan: Plan, answer: str) -> Outcome:
        """Turn the model's answer into an action to run, or the words to say instead.

        An action is run only if the call's state permits it and every value it needs is valid
        and was said by the caller; a missing value becomes a follow-up question. A verified
        caller may get any banking action, even one outside the turn's focused skill; before
        verification only the skill's own actions are possible, and anything else is answered by
        asking for the caller's details.
        """
        permitted = NODE_ACTIONS["assist"] if self.verified else plan.allowed
        action = parse_action(answer, permitted)
        if action is None:
            if not _is_action(answer):
                return Outcome()
            name = answer.split(maxsplit=2)[1] if len(answer.split()) > 1 else ""
            if not self.verified and name in ACTIONS:
                return Outcome(say=VERIFY_FIRST, reason=f"{name} needs a verified caller")
            return Outcome(say=DIDNT_CATCH, reason="unusable action line")
        if action.tool == "end_call" and not _GOODBYE.search(plan.text):
            return Outcome(say=ANYTHING_ELSE, reason="the caller hasn't said goodbye")
        action = self._grounded(action, plan.text)
        if not action.complete:
            return Outcome(
                say=clarifying_question(action), reason="missing " + ", ".join(action.missing)
            )
        return Outcome(action=action)

    def record(self, text: str, plan: Plan, action: Action | None, spoken: str) -> None:
        if action and action.tool == "verify_identity":
            self.verified = True
        self._remember(plan.text or text, spoken)

    def _grounded(self, action: Action, text: str) -> Action:
        said = " ".join(
            [m["content"] for m in self.history if m["role"] == "user"] + [text]
        ).replace(" ", "")
        ungrounded = tuple(
            name
            for name in GROUNDED
            if name in action.arguments
            and not re.search(rf"(?<!\d){action.arguments[name]}(?!\d)", said)
        )
        if not ungrounded:
            return action
        arguments = {k: v for k, v in action.arguments.items() if k not in ungrounded}
        return Action(action.tool, arguments, tuple(dict.fromkeys(action.missing + ungrounded)))

    def _messages(self, system: str, text: str) -> list[dict]:
        return [
            {"role": "system", "content": system},
            *self.history,
            {"role": "user", "content": text},
        ]

    def _remember(self, text: str, spoken: str) -> None:
        # Only what was said goes into the context; ACTION lines never do.
        self.history += [
            {"role": "user", "content": text},
            {"role": "assistant", "content": spoken},
        ]


def _is_action(answer: str) -> bool:
    return answer.strip().startswith("ACTION")


class RouterBrain(SinglePromptBrain):
    name = "router"

    def __init__(
        self,
        classifier: Classifier,
        today: date,
        verified: bool = False,
        history: list[dict] | None = None,
    ):
        super().__init__(today, verified, history)
        self.classifier = classifier
        self.session = Session(verified=verified)

    def plan(self, heard: str) -> Plan:
        text = understand(heard, self.today)
        start = perf_counter()
        route = self.session.route(self.classifier.predict(heard))
        route_s = perf_counter() - start
        if route.skill == FALLBACK_SKILL:
            system = build_system_prompt(self.today, FALLBACK_SKILL, "actions")
            allowed = NODE_ACTIONS[FALLBACK_SKILL]
        else:
            system = build_skill_prompt(route.skill, self.today, self.session.verified)
            allowed = SKILL_ACTIONS[route.skill]
        return Plan(
            self._messages(system, text),
            allowed,
            route.skill,
            route_s,
            route.reason,
            route.prediction.intent,
            route.prediction.score,
            heard,
            text,
            mid_sentence(text, self.session.verified),
        )

    def record(self, text: str, plan: Plan, action: Action | None, spoken: str) -> None:
        self.session.record(plan.step, action, spoken)
        self.verified = self.session.verified
        self._remember(plan.text or text, spoken)
