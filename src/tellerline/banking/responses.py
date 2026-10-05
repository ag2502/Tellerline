"""What the agent says after a tool runs.

The LLM decides which tool to call; these templates speak the result. Balances, dates, card
digits and references therefore come straight from the bank's data, never from generated
text, and the caller hears them without waiting for a second LLM pass.

Each template opens with a short clause that is the same on every call ("I've frozen that card
for you."), and the details follow. The opening already tells the caller what happened, and
because it never changes, its audio is rendered once at start-up (``FIXED_PHRASES``) and the
reply starts without waiting for text-to-speech.
"""

from collections.abc import Callable
from datetime import date
from typing import Any

from tellerline import speech

Template = Callable[[dict[str, Any], dict[str, Any], date], str]

ACCOUNTS = ("current", "savings")

VERIFIED = "you're verified."
VERIFIED_FOLLOW_UP = "What can I help you with?"
NOT_MATCHED = (
    "Sorry, those details don't match our records. "
    "Could you check your customer number and date of birth for me?"
)
FROZEN = "I've frozen that card for you."
OFFER_REPLACEMENT = "Would you like me to order a replacement?"
UNFROZEN = "I've unfrozen that card for you."
NOT_FROZEN = "That card isn't frozen."
CANT_UNFREEZE = "Sorry, I can't unfreeze that card."
CARD_ACTIVE = "That card is active."
CARD_FROZEN = "That card is frozen."
REPLACEMENT_ORDERED = "I've ordered you a replacement card."
DISPUTE_OPENED = "I've opened a dispute for that payment."
TRANSFERRING = "I'm transferring you to a colleague now."
GOODBYE = "Thanks for calling Tellerline Bank. Goodbye."
CARD_NOT_FOUND = "Sorry, I can't find that card."
CHECK_DIGITS = "Could you check the last four digits for me?"
ANOTHER_ACCOUNT = "Is there another account I can help with?"
DISPUTE_TOO_OLD = (
    "I can only open disputes for payments in the last year. "
    "Could you check the date of the payment?"
)
LOST_DETAILS = "Sorry, I've lost track of your details. I'll transfer you to a colleague."


def _on_account(account: str) -> str:
    return f"On your {account} account,"


def _verify_identity(args: dict, result: dict, today: date) -> str:
    if result.get("verified"):
        return f"Thanks, {result['first_name']}, {VERIFIED} {VERIFIED_FOLLOW_UP}"
    return NOT_MATCHED


def _get_balance(args: dict, result: dict, today: date) -> str:
    account = args.get("account", "current")
    text = f"{_on_account(account)} the balance is {speech.euro(result['balance_eur'])}."
    if result.get("available_eur") is not None and result["available_eur"] != result["balance_eur"]:
        text += f" You have {speech.euro(result['available_eur'])} available to spend."
    return text


def _transaction(item: dict, today: date) -> str:
    amount = speech.euro(item["amount_eur"])
    when = speech.spoken_date(item["date"], today)
    if item["amount_eur"] < 0:
        return f"{amount} to {item['merchant']} on {when}"
    return f"{amount} in from {item['merchant']} on {when}"


def _get_recent_transactions(args: dict, result: dict, today: date) -> str:
    items = result.get("transactions", [])
    account = args.get("account", "current")
    if not items:
        return f"{_on_account(account)} there are no recent transactions."
    if len(items) == 1:
        heading = "your last transaction was"
    else:
        heading = f"your last {speech.number(len(items))} transactions were"
    spoken = speech.join_list([_transaction(item, today) for item in items])
    return f"{_on_account(account)} {heading}: {spoken}."


def _freeze_card(args: dict, result: dict, today: date) -> str:
    card = speech.digits(args["card_last_four"])
    return f"{FROZEN} It's the card ending {card}, so it can't be used now. {OFFER_REPLACEMENT}"


_WHY_FROZEN = {
    "lost": "it was reported lost",
    "stolen": "it was reported stolen",
    "suspicious_activity": "of payments that looked suspicious",
    "temporary": "you asked for a temporary block",
}


def _why_frozen(result: dict) -> str:
    return _WHY_FROZEN.get(result.get("freeze_reason"), "of a security block")


def _unfreeze_card(args: dict, result: dict, today: date) -> str:
    card = speech.digits(args["card_last_four"])
    if result.get("changed"):
        return f"{UNFROZEN} The card ending {card} can be used again."
    if result.get("status") == "frozen":
        return (
            f"{CANT_UNFREEZE} It was frozen because {_why_frozen(result)}, so for your safety it "
            f"has to be replaced instead. {OFFER_REPLACEMENT}"
        )
    return f"{NOT_FROZEN} The card ending {card} is working normally."


def _get_card_status(args: dict, result: dict, today: date) -> str:
    card = speech.digits(args["card_last_four"])
    if result.get("status") == "frozen":
        text = f"{CARD_FROZEN} The card ending {card} was frozen because {_why_frozen(result)}."
    else:
        text = f"{CARD_ACTIVE} The card ending {card} is working normally."
    if result.get("replacement_arrives_by"):
        when = speech.spoken_date(result["replacement_arrives_by"], today)
        text += f" A replacement is on its way and should arrive by {when}."
    return text


def _order_replacement_card(args: dict, result: dict, today: date) -> str:
    card = speech.digits(args["card_last_four"])
    days = speech.number(result.get("arrives_in_working_days", 5))
    return (
        f"{REPLACEMENT_ORDERED} It replaces the card ending {card}, "
        f"and it should arrive within {days} working days."
    )


def _dispute_transaction(args: dict, result: dict, today: date) -> str:
    amount = speech.euro(args["amount"])
    when = speech.spoken_date(args["date"], today)
    reference = speech.digits(result["case_reference"])
    return (
        f"{DISPUTE_OPENED} That's the {amount} payment to {args['merchant']} on {when}, "
        f"and your reference is {reference}."
    )


def _transfer_to_human(args: dict, result: dict, today: date) -> str:
    minutes = result.get("estimated_wait_minutes")
    wait = f" The wait is about {speech.number(minutes)} minutes." if minutes else ""
    return f"{TRANSFERRING}{wait}"


def _end_call(args: dict, result: dict, today: date) -> str:
    return GOODBYE


TEMPLATES: dict[str, Template] = {
    "verify_identity": _verify_identity,
    "get_balance": _get_balance,
    "get_recent_transactions": _get_recent_transactions,
    "freeze_card": _freeze_card,
    "unfreeze_card": _unfreeze_card,
    "get_card_status": _get_card_status,
    "order_replacement_card": _order_replacement_card,
    "dispute_transaction": _dispute_transaction,
    "transfer_to_human": _transfer_to_human,
    "end_call": _end_call,
}


def _card_not_found(args: dict) -> str:
    card = speech.digits(args.get("card_last_four", ""))
    return f"{CARD_NOT_FOUND} There's no card ending {card} on your account. {CHECK_DIGITS}"


def _no_such_account(account: str) -> str:
    return f"Sorry, I can't see a {account} account in your name."


ERRORS: dict[str, Callable[[dict], str]] = {
    "card_not_found": _card_not_found,
    "account_not_found": lambda args: (
        f"{_no_such_account(args.get('account', 'that'))} {ANOTHER_ACCOUNT}"
    ),
    "dispute_date_out_of_range": lambda args: DISPUTE_TOO_OLD,
    "customer_not_found": lambda args: LOST_DETAILS,
}

# Sentences spoken word for word on many calls; the agent renders them once at start-up.
FIXED_PHRASES: tuple[str, ...] = (
    VERIFIED,
    VERIFIED_FOLLOW_UP,
    NOT_MATCHED,
    FROZEN,
    OFFER_REPLACEMENT,
    UNFROZEN,
    NOT_FROZEN,
    CANT_UNFREEZE,
    CARD_ACTIVE,
    CARD_FROZEN,
    REPLACEMENT_ORDERED,
    DISPUTE_OPENED,
    TRANSFERRING,
    GOODBYE,
    CARD_NOT_FOUND,
    CHECK_DIGITS,
    ANOTHER_ACCOUNT,
    DISPUTE_TOO_OLD,
    LOST_DETAILS,
    *(_on_account(account) for account in ACCOUNTS),
    *(_no_such_account(account) for account in ACCOUNTS),
)


def respond(tool: str, args: dict[str, Any], result: dict[str, Any], today: date) -> str:
    """The sentence(s) the agent speaks after ``tool`` ran with ``args`` and returned ``result``."""
    if "error" in result:
        return ERRORS[result["error"]](args)
    return TEMPLATES[tool](args, result, today)
