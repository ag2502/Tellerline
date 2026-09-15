import pytest

from tellerline.actions import Action
from tellerline.router.classifier import Prediction
from tellerline.router.session import Session


def predict(intent: str, confident: bool = True) -> Prediction:
    return Prediction(intent, 0.9 if confident else 0.5, 0.1, confident, {})


@pytest.mark.parametrize("intent", ["accounts", "cards", "disputes", "identity"])
def test_unverified_callers_only_reach_identity(intent):
    assert Session(verified=False).route(predict(intent)).skill == "identity"


def test_unverified_caller_can_reach_general_for_a_person_or_goodbye():
    assert Session(verified=False).route(predict("general")).skill == "general"


def test_confident_intent_routes_when_nothing_is_open():
    assert Session(verified=True).route(predict("cards")).skill == "cards"


def test_unconfident_turn_uses_the_full_prompt_when_nothing_is_open():
    assert Session(verified=True).route(predict("cards", confident=False)).skill == "assist"


def test_open_task_keeps_unconfident_answers():
    session = Session(verified=True, open_skill="cards")
    assert session.route(predict("identity", confident=False)).skill == "cards"


def test_open_task_switches_on_confident_new_topic():
    session = Session(verified=True, open_skill="cards")
    assert session.route(predict("accounts")).skill == "accounts"


def test_reply_leaves_the_skill_open():
    session = Session(verified=True)
    session.record("cards", None, "What are the last four digits of the card?")
    assert session.open_skill == "cards"


def test_completed_action_closes_the_skill():
    session = Session(verified=True, open_skill="accounts")
    session.record("accounts", Action("get_balance", {}), "The balance is ten euro.")
    assert session.open_skill is None


def test_result_that_asks_a_question_keeps_the_skill_open():
    session = Session(verified=True)
    freeze = Action("freeze_card", {"card_last_four": "1234"})
    session.record("cards", freeze, "I've frozen it. Would you like a replacement?")
    assert session.open_skill == "cards"


def test_verification_marks_verified_and_closes_identity():
    session = Session(verified=False, open_skill="identity")
    session.record("identity", Action("verify_identity", {}), "You're verified. What can I do?")
    assert session.verified
    assert session.open_skill is None


@pytest.mark.parametrize("tool", ["transfer_to_human", "end_call"])
def test_transfer_and_end_close_the_task(tool):
    session = Session(verified=True, open_skill="general")
    session.record("general", Action(tool, {}), "Transferring you now?")
    assert session.open_skill is None
