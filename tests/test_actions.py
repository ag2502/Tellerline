import pytest

from tellerline.actions import (
    ACTIONS,
    NODE_ACTIONS,
    Action,
    action_instructions,
    clarifying_question,
    parse_action,
)
from tellerline.banking.responses import TEMPLATES


def test_every_action_maps_to_a_banking_operation_with_a_template():
    assert {spec.tool for spec in ACTIONS.values()} == set(TEMPLATES)


def test_plain_reply_is_not_an_action():
    assert parse_action("Could I have your customer number, please?") is None


def test_freeze_with_reason_mapping():
    assert parse_action("ACTION freeze card=4217 reason=suspicious") == Action(
        "freeze_card", {"card_last_four": "4217", "reason": "suspicious_activity"}
    )


def test_leading_zeros_survive():
    assert parse_action("ACTION replace card=0093").arguments == {"card_last_four": "0093"}


def test_quoted_merchant_and_numbers():
    action = parse_action('ACTION dispute merchant="Bean There Cafe" amount=15.50 date=2026-09-11')
    assert action == Action(
        "dispute_transaction",
        {"merchant": "Bean There Cafe", "amount": 15.5, "date": "2026-09-11"},
    )


def test_count_is_an_integer_and_unknown_keys_are_ignored():
    action = parse_action("ACTION transactions account=savings count=5 colour=blue")
    assert action.arguments == {"account": "savings", "count": 5}


def test_bad_numbers_are_dropped_and_defaults_filled():
    assert parse_action("ACTION transactions account=current count=five").arguments == {
        "account": "current",
        "count": 3,
    }


def test_copied_placeholders_count_as_missing():
    action = parse_action("ACTION verify customer=<8 digits> dob=<YYYY-MM-DD>")
    assert action.tool == "verify_identity"
    assert action.missing == ("customer_number", "date_of_birth")
    assert not action.complete


@pytest.mark.parametrize(
    ("line", "missing"),
    [
        ("ACTION verify customer=1234567 dob=1990-01-01", ("customer_number",)),
        ("ACTION verify customer=12345678 dob=1990-02-30", ("date_of_birth",)),
        ("ACTION freeze card=12345 reason=lost", ("card_last_four",)),
        ("ACTION balance account=cheque", ("account",)),
        ('ACTION dispute merchant="Aldi" amount=-5 date=2026-09-01', ("amount",)),
    ],
)
def test_invalid_values_are_missing(line, missing):
    assert parse_action(line).missing == missing


@pytest.mark.parametrize(
    ("line", "question"),
    [
        ("ACTION verify customer=30118842", "Could you tell me your date of birth, please?"),
        ("ACTION freeze reason=stolen", "What are the last four digits of the card?"),
        ("ACTION balance", "Is that your current account or your savings account?"),
        (
            'ACTION dispute merchant="Pizza Palace"',
            "Could you tell me how much it was and the date it went out, please?",
        ),
    ],
)
def test_clarifying_questions(line, question):
    assert clarifying_question(parse_action(line)) == question


def test_freeze_reason_defaults_to_lost():
    assert parse_action("ACTION freeze card=4217").arguments["reason"] == "lost"


def test_action_line_can_follow_other_text():
    assert parse_action("Sure.\nACTION transfer").tool == "transfer_to_human"


def test_unknown_action_is_rejected():
    assert parse_action("ACTION launch rockets=3") is None


@pytest.mark.parametrize(
    "line", ["ACTION balance account=current", "ACTION freeze card=1 reason=lost"]
)
def test_banking_actions_are_rejected_before_verification(line):
    assert parse_action(line, NODE_ACTIONS["identify"]) is None
    assert parse_action(line, NODE_ACTIONS["assist"]) is not None


def test_instructions_list_only_the_steps_actions():
    identify = action_instructions(NODE_ACTIONS["identify"])
    assert "ACTION verify" in identify
    assert "ACTION balance" not in identify
    assert set(NODE_ACTIONS) == {"identify", "assist"}
