from datetime import date

from tellerline import speech
from tellerline.banking.responses import TEMPLATES, respond
from tellerline.banking.tools import TOOL_NAMES

TODAY = date(2026, 9, 14)


def test_euro_amounts():
    assert speech.euro(1250.40) == "one thousand, two hundred and fifty euro and forty cent"
    assert speech.euro(-42.17) == "forty-two euro and seventeen cent"
    assert speech.euro(120) == "one hundred and twenty euro"
    assert speech.euro(0.99) == "ninety-nine cent"
    assert speech.euro(89.5) == "eighty-nine euro and fifty cent"


def test_euro_rounds_to_the_cent():
    assert speech.euro(19.999) == "twenty euro"


def test_dates_drop_the_current_year():
    assert speech.spoken_date("2026-09-12", TODAY) == "the twelfth of September"
    assert speech.spoken_date(date(2025, 3, 1), TODAY) == "the first of March twenty twenty-five"
    assert speech.spoken_date("1991-03-03") == "the third of March nineteen ninety-one"


def test_digits_and_references():
    assert speech.digits("0093") == "zero zero nine three"
    assert speech.digits("DSP-20417") == "D S P two zero four one seven"


def test_join_list():
    assert speech.join_list(["a"]) == "a"
    assert speech.join_list(["a", "b", "c"]) == "a, b, and then c"


def test_every_tool_has_a_template():
    assert set(TEMPLATES) == TOOL_NAMES


def test_balance_response_has_no_digits():
    text = respond(
        "get_balance",
        {"account": "current"},
        {"balance_eur": 1250.40, "available_eur": 1180.40},
        TODAY,
    )
    assert text.startswith("The balance on your current account is one thousand, two hundred")
    assert not any(ch.isdigit() for ch in text)


def test_transactions_response():
    result = {
        "transactions": [
            {"date": "2026-09-12", "merchant": "Tesco Rathmines", "amount_eur": -42.17},
            {"date": "2026-09-11", "merchant": "Acme Ltd", "amount_eur": 2650.00},
        ]
    }
    text = respond("get_recent_transactions", {"account": "current"}, result, TODAY)
    assert "your last two transactions" in text
    assert (
        "forty-two euro and seventeen cent to Tesco Rathmines on the twelfth of September" in text
    )
    assert "in from Acme Ltd" in text
    assert not any(ch.isdigit() for ch in text)


def test_failed_verification_does_not_reveal_details():
    text = respond(
        "verify_identity",
        {"customer_number": "1", "date_of_birth": "2000-01-01"},
        {"verified": False},
        TODAY,
    )
    assert "don't match" in text


def test_card_and_dispute_responses_speak_codes_as_words():
    freeze = respond(
        "freeze_card", {"card_last_four": "4217", "reason": "lost"}, {"status": "frozen"}, TODAY
    )
    assert "four two one seven" in freeze
    dispute = respond(
        "dispute_transaction",
        {"merchant": "StreamFlix", "amount": 49.99, "date": "2026-09-02"},
        {"case_reference": "DSP-20417"},
        TODAY,
    )
    assert (
        "forty-nine euro and ninety-nine cent payment to StreamFlix on the second of September"
        in dispute
    )
    assert not any(ch.isdigit() for ch in dispute)
