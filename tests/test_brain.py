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
    assert plan.allowed == ("freeze", "unfreeze", "status", "replace", "transfer", "end")
    assert "help with the caller's card" in plan.messages[0]["content"]


def test_router_keeps_open_task_for_unconfident_answer():
    brain = RouterBrain(FakeClassifier("cards"), TODAY, verified=True)
    plan = brain.plan("I lost my card")
    brain.record("I lost my card", plan, None, "What are the last four digits?")
    brain.classifier = FakeClassifier("identity", confident=False)
    assert brain.plan("It ends 4217").step == "cards"


def test_a_withdrawn_turn_leaves_only_what_was_heard():
    brain = SinglePromptBrain(TODAY, verified=True)
    plan = brain.plan("Balance please")
    brain.record("Balance please", plan, None, "Which account?")
    heard = list(brain.history)
    plan = brain.plan("Pause my card ending 7780")
    brain.record("Pause my card ending 7780", plan, None, "Which card is it?")
    brain.withdraw()
    assert brain.history == heard
    brain.withdraw()
    brain.withdraw()  # the greeting was heard: nothing before this brain's turns goes
    assert [m["content"] for m in brain.history] == ["Hello?", GREETING]


def test_a_withdrawn_question_leaves_no_task_waiting_but_verification_stays():
    brain = RouterBrain(FakeClassifier("identity"), TODAY)
    plan = brain.plan("My number is 45127890, born 3 March 1991.")
    brain.record("...", plan, Action("verify_identity", {}), "Thanks, Aoife, you're verified.")
    brain.withdraw()
    assert brain.verified and brain.session.verified  # the bank verified them

    brain.classifier = FakeClassifier("cards")
    plan = brain.plan("Pause my card for a bit")
    brain.record("Pause my card for a bit", plan, None, "Which card is it?")
    assert brain.session.open_skill == "cards"
    brain.withdraw()
    assert brain.session.open_skill is None


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


def test_half_the_identity_details_holds_the_reply():
    from tellerline.brain import half_identified

    assert half_identified("My customer number is 45127890.", "", TODAY)
    assert half_identified("Born the 3rd of March 1991 (1991-03-03).", "", TODAY)
    both = "It's 45127890, born the 3rd of March 1991 (1991-03-03)."
    assert not half_identified(both, "", TODAY)
    # The number came in an earlier turn: the date completes the details.
    assert not half_identified("Born 1991 (1991-03-03).", "My number is 45127890.", TODAY)
    # "Yesterday" is a date, but not a date of birth.
    assert not half_identified("It was yesterday (2026-09-13).", "", TODAY)
    assert not half_identified("I've lost my card.", "", TODAY)

    unverified = SinglePromptBrain(TODAY)
    assert unverified.plan("My customer number is 4 5 1 2 7 8 9 0").hold
    assert unverified.plan("It's four five one two. seven eight nine zero").hold
    assert not unverified.plan("My customer number is 45127890, born 3/3/1991").hold
    assert not unverified.plan("What's the weather like today?").hold
    verified = SinglePromptBrain(TODAY, verified=True)
    assert not verified.plan("My card ending 4217 cost me 45127890 euro").hold


def test_a_label_without_its_value_holds_the_reply():
    from tellerline.brain import mid_sentence

    assert mid_sentence("My customer number.", verified=False)
    assert mid_sentence("The card ends in", verified=True)
    assert mid_sentence("It's the card ending", verified=True)
    assert not mid_sentence("I lost my card.", verified=True)
    assert not mid_sentence("What's my account number?", verified=True)
