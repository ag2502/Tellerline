"""Write numbers, money, dates and codes the way a British English speaker says them.

Text-to-speech reads "€1,250.40" or "2026-09-12" unpredictably, so anything spoken to the
caller is written out in words first.
"""

from datetime import date

from num2words import num2words

_DIGITS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]


def number(value: int) -> str:
    """1250 -> 'one thousand, two hundred and fifty'."""
    return num2words(value, lang="en_GB")


def euro(amount: float) -> str:
    """1250.4 -> 'one thousand, two hundred and fifty euro and forty cent'. Sign is ignored."""
    cents_total = round(abs(amount) * 100)
    whole, cents = divmod(cents_total, 100)
    if whole and cents:
        return f"{number(whole)} euro and {number(cents)} cent"
    if cents:
        return f"{number(cents)} cent"
    return f"{number(whole)} euro"


def spoken_date(value: date | str, today: date | None = None) -> str:
    """2026-09-12 -> 'the twelfth of September', adding the year when it isn't this year."""
    if isinstance(value, str):
        value = date.fromisoformat(value)
    spoken = f"the {num2words(value.day, to='ordinal', lang='en_GB')} of {value:%B}"
    if today is None or value.year != today.year:
        spoken += f" {num2words(value.year, to='year', lang='en_GB')}"
    return spoken


def digits(value: str) -> str:
    """'4217' -> 'four two one seven'. Non-digits are spoken as letters, e.g. 'DSP'."""
    return " ".join(
        _DIGITS[int(ch)] if ch.isdigit() else ch.upper() for ch in value if ch.isalnum()
    )


def join_list(items: list[str]) -> str:
    """['a', 'b', 'c'] -> 'a, b, and then c'."""
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + ", and then " + items[-1]
