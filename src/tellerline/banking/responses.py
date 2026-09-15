"""What the agent says after a tool runs.

The LLM decides which tool to call; these templates speak the result. Balances, dates, card
digits and references therefore come straight from the bank's data, never from generated
text, and the caller hears them without waiting for a second LLM pass.
"""

from collections.abc import Callable
from datetime import date
from typing import Any

from tellerline import speech

Template = Callable[[dict[str, Any], dict[str, Any], date], str]


def _verify_identity(args: dict, result: dict, today: date) -> str:
    if result.get("verified"):
        return f"Thanks, {result['first_name']}, you're verified. What can I help you with?"
    return (
        "Sorry, those details don't match our records. "
        "Could you check your customer number and date of birth for me?"
    )


def _get_balance(args: dict, result: dict, today: date) -> str:
    account = args.get("account", "current")
    text = f"The balance on your {account} account is {speech.euro(result['balance_eur'])}."
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
        return f"There are no recent transactions on your {account} account."
    count = (
        "your last transaction"
        if len(items) == 1
        else f"your last {speech.number(len(items))} transactions"
    )
    spoken = speech.join_list([_transaction(item, today) for item in items])
    return f"On your {account} account, {count}: {spoken}."


def _freeze_card(args: dict, result: dict, today: date) -> str:
    card = speech.digits(args["card_last_four"])
    return (
        f"I've frozen the card ending {card}, so it can't be used. "
        "Would you like me to order a replacement?"
    )


def _order_replacement_card(args: dict, result: dict, today: date) -> str:
    card = speech.digits(args["card_last_four"])
    days = speech.number(result.get("arrives_in_working_days", 5))
    return (
        f"I've ordered a replacement for the card ending {card}. "
        f"It should arrive within {days} working days."
    )


def _dispute_transaction(args: dict, result: dict, today: date) -> str:
    amount = speech.euro(args["amount"])
    when = speech.spoken_date(args["date"], today)
    reference = speech.digits(result["case_reference"])
    return (
        f"I've opened a dispute for the {amount} payment to {args['merchant']} on {when}. "
        f"Your reference is {reference}."
    )


def _transfer_to_human(args: dict, result: dict, today: date) -> str:
    minutes = result.get("estimated_wait_minutes")
    wait = f" The wait is about {speech.number(minutes)} minutes." if minutes else ""
    return f"I'm transferring you to a colleague now.{wait}"


def _end_call(args: dict, result: dict, today: date) -> str:
    return "Thanks for calling Tellerline Bank. Goodbye."


TEMPLATES: dict[str, Template] = {
    "verify_identity": _verify_identity,
    "get_balance": _get_balance,
    "get_recent_transactions": _get_recent_transactions,
    "freeze_card": _freeze_card,
    "order_replacement_card": _order_replacement_card,
    "dispute_transaction": _dispute_transaction,
    "transfer_to_human": _transfer_to_human,
    "end_call": _end_call,
}


def respond(tool: str, args: dict[str, Any], result: dict[str, Any], today: date) -> str:
    """The sentence(s) the agent speaks after ``tool`` ran with ``args`` and returned ``result``."""
    return TEMPLATES[tool](args, result, today)
