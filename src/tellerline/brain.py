"""The agent's decision step, independent of audio.

For each caller turn a brain builds the LLM messages and says which actions the model may take;
after the turn it records what the caller heard and updates the call's state. The voice
pipeline (Phase 1) and the benchmarks both drive these classes.

- ``SinglePromptBrain``: one prompt for the whole call, switching from the identify step to the
  assist step once the caller is verified.
- ``RouterBrain``: a CPU intent classifier and session rules pick one focused skill prompt per
  turn (``tellerline.router``).
"""

from dataclasses import dataclass
from datetime import date
from time import perf_counter
from typing import Protocol

from tellerline.actions import NODE_ACTIONS, Action
from tellerline.prompts import build_system_prompt
from tellerline.router.classifier import Prediction
from tellerline.router.session import FALLBACK_SKILL, Session
from tellerline.router.skills import SKILL_ACTIONS, build_skill_prompt

GREETING = (
    "Hello, you're through to Tellerline Bank. I'm an AI assistant. How can I help you today?"
)


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


def opening_history() -> list[dict]:
    """The call so far when the caller first speaks: they said hello and heard the greeting."""
    return [{"role": "user", "content": "Hello?"}, {"role": "assistant", "content": GREETING}]


class SinglePromptBrain:
    name = "single"

    def __init__(self, today: date, verified: bool = False, history: list[dict] | None = None):
        self.today = today
        self.verified = verified
        self.history = list(history if history is not None else opening_history())

    def plan(self, text: str) -> Plan:
        step = "assist" if self.verified else "identify"
        system = build_system_prompt(self.today, step, "actions")
        return Plan(self._messages(system, text), NODE_ACTIONS[step], step)

    def record(self, text: str, plan: Plan, action: Action | None, spoken: str) -> None:
        if action and action.tool == "verify_identity":
            self.verified = True
        self._remember(text, spoken)

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

    def plan(self, text: str) -> Plan:
        start = perf_counter()
        route = self.session.route(self.classifier.predict(text))
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
        )

    def record(self, text: str, plan: Plan, action: Action | None, spoken: str) -> None:
        self.session.record(plan.step, action, spoken)
        self.verified = self.session.verified
        self._remember(text, spoken)
