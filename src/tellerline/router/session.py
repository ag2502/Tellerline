"""Decide which skill handles each caller turn, using the classifier and the call's state.

Rules, in order:

1. Before verification only the identity and general skills are reachable, so no banking
   action can run for an unverified caller whatever the model writes.
2. If a skill asked the caller a question last turn, it keeps the conversation unless the
   classifier is confident the caller has moved to a different banking topic. Short answers such
   as "it ends 4217" or "yes please" stay with the open task even when the classifier reads them
   confidently as small talk: every verified skill can also transfer the caller or end the call.
3. Otherwise the classifier's intent wins when it is confident; anything else goes to the full
   prompt with every action (``assist``).

The classifier runs on every turn because it costs milliseconds on the CPU; what the session
avoids is switching tasks on a weak signal.
"""

from dataclasses import dataclass

from tellerline.actions import Action
from tellerline.router.classifier import Prediction
from tellerline.router.skills import UNVERIFIED_SKILLS

CLOSING_TOOLS = frozenset({"verify_identity", "transfer_to_human", "end_call"})
# When unsure what a verified caller wants, use the full single prompt with every action rather
# than guessing a specialist: a specialist when confident, a generalist when not.
FALLBACK_SKILL = "assist"


@dataclass(frozen=True)
class Route:
    skill: str
    reason: str
    prediction: Prediction


@dataclass
class Session:
    verified: bool = False
    open_skill: str | None = None

    def route(self, prediction: Prediction) -> Route:
        intent = prediction.intent if prediction.confident else None

        if not self.verified:
            if intent == "general":
                return Route("general", "unverified: confident general intent", prediction)
            if self.open_skill in UNVERIFIED_SKILLS and intent is None:
                return Route(self.open_skill, "unverified: continuing open task", prediction)
            return Route("identity", "unverified: verify first", prediction)

        if self.open_skill and intent in (None, self.open_skill, "general"):
            return Route(self.open_skill, "continuing open task", prediction)
        if intent and intent != "identity":
            return Route(intent, "confident intent", prediction)
        return Route(FALLBACK_SKILL, "no confident intent: full prompt", prediction)

    def record(self, skill: str, action: Action | None, spoken: str) -> None:
        """Update state after the agent's turn.

        A skill stays open while it's waiting on the caller: it replied instead of acting, or
        its spoken result ended with a question (such as offering a replacement card).
        Verification, transfers and ending the call always close the task.
        """
        if action and action.tool in CLOSING_TOOLS:
            self.verified = self.verified or action.tool == "verify_identity"
            self.open_skill = None
            return
        waiting = action is None or spoken.rstrip().endswith("?")
        self.open_skill = skill if waiting else None
