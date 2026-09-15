from datetime import date

from tellerline.actions import Action
from tellerline.brain import GREETING, RouterBrain, SinglePromptBrain
from tellerline.router.classifier import Prediction

TODAY = date(2026, 9, 14)


class FakeClassifier:
    def __init__(self, intent: str, confident: bool = True):
        self.intent, self.confident = intent, confident

    def predict(self, text: str) -> Prediction:
        return Prediction(self.intent, 0.9 if self.confident else 0.4, 0.2, self.confident, {})


def test_single_prompt_switches_step_after_verification():
    brain = SinglePromptBrain(TODAY)
    plan = brain.plan("My number is 12345678, born 1 May 1990.")
    assert plan.step == "identify"
    assert "balance" not in plan.allowed
    brain.record("...", plan, Action("verify_identity", {}), "Thanks, you're verified.")
    assert brain.plan("What's my balance?").step == "assist"


def test_history_holds_what_was_said_not_action_lines():
    brain = SinglePromptBrain(TODAY, verified=True)
    plan = brain.plan("Balance please")
    brain.record("Balance please", plan, Action("get_balance", {}), "The balance is ten euro.")
    contents = [m["content"] for m in brain.history]
    assert contents[1] == GREETING
    assert contents[-1] == "The balance is ten euro."
    assert not any("ACTION" in c for c in contents)


def test_messages_are_system_history_then_caller():
    plan = SinglePromptBrain(TODAY).plan("Hi")
    roles = [m["role"] for m in plan.messages]
    assert roles == ["system", "user", "assistant", "user"]


def test_router_picks_skill_prompt_and_actions():
    brain = RouterBrain(FakeClassifier("cards"), TODAY, verified=True)
    plan = brain.plan("I lost my card")
    assert plan.step == "cards"
    assert plan.allowed == ("freeze", "replace", "transfer", "end")
    assert "help with the caller's card" in plan.messages[0]["content"]


def test_router_keeps_open_task_for_unconfident_answer():
    brain = RouterBrain(FakeClassifier("cards"), TODAY, verified=True)
    plan = brain.plan("I lost my card")
    brain.record("I lost my card", plan, None, "What are the last four digits?")
    brain.classifier = FakeClassifier("identity", confident=False)
    assert brain.plan("It ends 4217").step == "cards"


def test_router_blocks_banking_skills_until_verified():
    brain = RouterBrain(FakeClassifier("accounts"), TODAY, verified=False)
    assert brain.plan("What's my balance?").step == "identity"


def test_router_falls_back_to_full_prompt_when_unsure():
    brain = RouterBrain(FakeClassifier("cards", confident=False), TODAY, verified=True)
    plan = brain.plan("Hmm, about that thing")
    assert plan.step == "assist"
    assert "balance" in plan.allowed and "freeze" in plan.allowed


def test_unverified_callers_cannot_be_transferred_from_the_identity_step():
    brain = RouterBrain(FakeClassifier("accounts", confident=False), TODAY, verified=False)
    assert brain.plan("Can you check my balance?").allowed == ("verify",)
