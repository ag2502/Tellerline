"""Prompt-only actions: the LLM writes an action line, code parses and runs it.

No tool-calling API is used. The system prompt lists each action and its exact syntax, with
examples. The model either replies to the caller in plain speech, or writes one line such as

    ACTION freeze card=4217 reason=lost

Code parses the line, runs the banking operation, and the caller hears the result from a
response template (``tellerline.banking.responses``).
"""

import re
from collections.abc import Callable, Collection
from dataclasses import dataclass, field
from datetime import date
from itertools import combinations
from typing import Any

from tellerline.banking.tools import ACCOUNTS, FREEZE_REASONS

PREFIX = "ACTION"


@dataclass(frozen=True)
class ActionSpec:
    name: str
    tool: str
    syntax: str
    when: str
    # Action key -> argument name used by the bank API and response templates.
    keys: dict[str, str] = field(default_factory=dict)
    numbers: frozenset[str] = frozenset()
    integers: frozenset[str] = frozenset()


ACTIONS: dict[str, ActionSpec] = {
    spec.name: spec
    for spec in [
        ActionSpec(
            "verify",
            "verify_identity",
            "verify customer=<8 digits> dob=<YYYY-MM-DD>",
            "as soon as the caller has given both their customer number and date of birth",
            {"customer": "customer_number", "dob": "date_of_birth"},
        ),
        ActionSpec(
            "balance",
            "get_balance",
            "balance account=<current or savings>",
            "when the caller asks how much money they have",
            {"account": "account"},
        ),
        ActionSpec(
            "transactions",
            "get_recent_transactions",
            "transactions account=<current or savings> count=<1 to 10, default 3>",
            "when the caller asks about recent payments, spending or activity",
            {"account": "account", "count": "count"},
            integers=frozenset({"count"}),
        ),
        ActionSpec(
            "freeze",
            "freeze_card",
            "freeze card=<last 4 digits> reason=<lost, stolen, suspicious or temporary>",
            "as soon as you know the card's last four digits; choose the reason yourself: lost if "
            "they can't find it, stolen if someone took it, suspicious for payments they don't "
            "recognise or details given to someone else, temporary if they expect to find it",
            {"card": "card_last_four", "reason": "reason"},
        ),
        ActionSpec(
            "replace",
            "order_replacement_card",
            "replace card=<last 4 digits>",
            "when the caller needs a new card and you know its last four digits",
            {"card": "card_last_four"},
        ),
        ActionSpec(
            "dispute",
            "dispute_transaction",
            'dispute merchant="<name>" amount=<euro> date=<YYYY-MM-DD>',
            "when the caller says a payment was wrong or not theirs and you know the merchant, "
            "amount and date; use this year if they don't say one",
            {"merchant": "merchant", "amount": "amount", "date": "date"},
            numbers=frozenset({"amount"}),
        ),
        ActionSpec(
            "transfer",
            "transfer_to_human",
            "transfer",
            "straight away when the caller asks for a person, advisor or manager",
        ),
        ActionSpec(
            "end",
            "end_call",
            "end",
            "when the caller says goodbye or that they have everything they need",
        ),
    ]
}

NODE_ACTIONS: dict[str, tuple[str, ...]] = {
    "identify": ("verify", "transfer", "end"),
    "assist": ("balance", "transactions", "freeze", "replace", "dispute", "transfer", "end"),
}

_REASONS = {"suspicious": "suspicious_activity"}
_ARGUMENT = re.compile(r'(\w+)=(?:"([^"]*)"|(\S+))')


def _iso_date(value: Any) -> bool:
    try:
        date.fromisoformat(value)
    except (TypeError, ValueError):
        return False
    return True


# A value that fails its check is treated as missing, so placeholders the model copied from the
# syntax ("<8 digits>") or half-heard numbers never reach the bank.
_VALID: dict[str, Callable[[Any], bool]] = {
    "customer_number": lambda v: bool(re.fullmatch(r"\d{8}", str(v))),
    "date_of_birth": _iso_date,
    "date": _iso_date,
    "card_last_four": lambda v: bool(re.fullmatch(r"\d{4}", str(v))),
    "account": lambda v: v in ACCOUNTS,
    "reason": lambda v: v in FREEZE_REASONS,
    "count": lambda v: isinstance(v, int) and 1 <= v <= 10,
    "amount": lambda v: isinstance(v, float) and v > 0,
    "merchant": lambda v: bool(str(v).strip()) and "<" not in str(v),
}
REQUIRED: dict[str, tuple[str, ...]] = {
    "verify_identity": ("customer_number", "date_of_birth"),
    "get_balance": ("account",),
    "get_recent_transactions": ("account",),
    "freeze_card": ("card_last_four",),
    "order_replacement_card": ("card_last_four",),
    "dispute_transaction": ("merchant", "amount", "date"),
    "transfer_to_human": (),
    "end_call": (),
}
DEFAULTS: dict[str, dict[str, Any]] = {
    "freeze_card": {"reason": "lost"},
    "get_recent_transactions": {"count": 3},
}
_ASK = {
    "customer_number": "your eight-digit customer number",
    "date_of_birth": "your date of birth",
    "merchant": "who the payment was to",
    "amount": "how much it was",
    "date": "the date it went out",
}


@dataclass(frozen=True)
class Action:
    tool: str
    arguments: dict[str, Any]
    missing: tuple[str, ...] = ()

    @property
    def complete(self) -> bool:
        return not self.missing


def clarifying_question(action: Action) -> str:
    """What to ask when the model chose the right action without everything it needs."""
    if "card_last_four" in action.missing:
        return "What are the last four digits of the card?"
    if "account" in action.missing:
        return "Is that your current account or your savings account?"
    parts = [_ASK[name] for name in action.missing]
    listed = parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]
    return f"Could you tell me {listed}, please?"


def common_questions() -> list[str]:
    """Every follow-up question ``clarifying_question`` can ask, for pre-rendering their audio."""
    questions: list[str] = []
    for tool, required in REQUIRED.items():
        for size in range(1, len(required) + 1):
            for missing in combinations(required, size):
                question = clarifying_question(Action(tool, {}, missing))
                if question not in questions:
                    questions.append(question)
    return questions


def action_instructions(names: Collection[str]) -> str:
    """The part of a system prompt that lists the given actions and when to use them."""
    return "\n".join(f"- {PREFIX} {ACTIONS[name].syntax}: {ACTIONS[name].when}." for name in names)


def parse_action(text: str, allowed: Collection[str] | None = None) -> Action | None:
    """Parse the first ``ACTION`` line in ``text``; None if there isn't one.

    Invalid values are dropped and defaults filled in. ``Action.missing`` lists what the action
    still needs; ``clarifying_question`` says how to ask the caller for it.

    With ``allowed``, other actions are rejected, so the flow rather than the model decides
    what can happen at each step (for example, nothing but verification before identity checks).
    """
    line = next((ln.strip() for ln in text.splitlines() if ln.strip().startswith(PREFIX)), None)
    if line is None:
        return None
    parts = line[len(PREFIX) :].split(maxsplit=1)
    if not parts or parts[0] not in ACTIONS:
        return None
    spec = ACTIONS[parts[0]]
    if allowed is not None and spec.name not in allowed:
        return None

    arguments: dict[str, Any] = {}
    for key, quoted, bare in _ARGUMENT.findall(parts[1] if len(parts) > 1 else ""):
        if key not in spec.keys:
            continue
        value: Any = quoted if quoted else bare.strip('",.')
        try:
            if key in spec.numbers:
                value = float(value.lstrip("€"))
            elif key in spec.integers:
                value = int(value)
        except ValueError:
            continue
        if key == "reason":
            value = _REASONS.get(value, value)
        name = spec.keys[key]
        if _VALID[name](value):
            arguments[name] = value
    for name, value in DEFAULTS.get(spec.tool, {}).items():
        arguments.setdefault(name, value)
    missing = tuple(name for name in REQUIRED[spec.tool] if name not in arguments)
    return Action(spec.tool, arguments, missing)


class ReplySplitter:
    """Tells, from the first characters of a streamed response, whether it's speech or an action.

    Speech is released as it arrives so text-to-speech can start on the first sentence; an
    ``ACTION`` line is held back whole for parsing. Only the few characters that could still be
    the start of "ACTION" are ever delayed.
    """

    def __init__(self) -> None:
        self.text = ""
        self.mode: str | None = None  # "speech" or "action" once decided

    @property
    def is_action(self) -> bool:
        return self.mode == "action"

    def feed(self, piece: str) -> str:
        """Add a streamed piece; return the speech that can be spoken now (possibly empty)."""
        self.text += piece
        if self.mode == "speech":
            return piece
        if self.mode == "action":
            return ""
        head = self.text.lstrip()
        if not head or (PREFIX.startswith(head) and len(head) < len(PREFIX)):
            return ""
        if head.startswith(PREFIX):
            self.mode = "action"
            return ""
        self.mode = "speech"
        return self.text

    def finish(self) -> str:
        """End of the stream: release anything still held back as speech."""
        if self.mode is None:
            self.mode = "speech"
            return self.text if self.text.strip() else ""
        return ""
