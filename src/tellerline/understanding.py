"""Turn what the caller said into text the model can't misread: digits, money and dates.

Speech recognition writes what it hears: "double seven four five", "34 euro 60", "last
Tuesday". Small models then copy the wrong digits, drop the cents, or count days wrong, and
those are exactly the values that reach the bank. This step rewrites them before the model sees
the turn, the same way every time:

- digits said as words, the British way included: "seven two oh six" and "double oh four one"
  become 7206 and 0041; digits read out one by one ("5 8 3 3 1 0 2 6") are joined;
- amounts become euro figures: "34 euro 60" is €34.60, "forty-five euro" is €45;
- every date is followed by the date it means: "last Tuesday (2026-09-08)",
  "14/07/1985 (1985-07-14)", "on the 3rd (2026-09-03)".

The model still decides what to do; it just no longer has to do the arithmetic.
"""

import re
from datetime import date, timedelta

_DIGIT_WORDS = {
    "zero": "0",
    "oh": "0",
    "nought": "0",
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "five": "5",
    "six": "6",
    "seven": "7",
    "eight": "8",
    "nine": "9",
}
_REPEATS = {"double": 2, "treble": 3, "triple": 3}
_DIGIT = "|".join(_DIGIT_WORDS)
# One digit said aloud: "seven", "7", or a repeat such as "double seven" or "double 7".
_SPOKEN_DIGIT = rf"(?:(?:double|treble|triple)\s+)?(?:{_DIGIT}|\d)"
# Two or more in a row that make at least three digits: a code being read out ("four two one
# seven", "treble three one"), not "one of them", "two, three" or "double seven".
_SPOKEN_DIGITS = re.compile(
    rf"\b{_SPOKEN_DIGIT}(?:[\s,-]+{_SPOKEN_DIGIT})+\b(?!\s*(?:euro|cent|%))", re.I
)
MIN_CODE_DIGITS = 3
# Two groups of four, as an eight-digit customer number is often read: "3011 8842".
# Groups of digits read with pauses between them ("4512. 7890", "573. 02918", "3011 8842"), which
# together make the eight digits of a customer number.
_DIGIT_GROUPS = re.compile(r"(?<!\d)(?<!\d\.)\b\d{1,7}(?:(?:[\s,-]|\.\s)+\d{1,7}\b)+(?!\d|\.\d)")
CUSTOMER_NUMBER_DIGITS = 8
# 14-07-1985, 14.07.85 or 2026-09-03 are dates, never a customer number read in groups.
_NUMERIC_DATE = re.compile(r"\d{1,2}[-/.]\d{1,2}[-/.](?:\d{2}|\d{4})|\d{4}-\d{2}-\d{2}")

_UNITS = {
    word: value
    for value, word in enumerate(
        [
            "zero",
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
            "ten",
            "eleven",
            "twelve",
            "thirteen",
            "fourteen",
            "fifteen",
            "sixteen",
            "seventeen",
            "eighteen",
            "nineteen",
        ]
    )
}
_TENS = {
    word: (index + 2) * 10
    for index, word in enumerate(
        ["twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
    )
}
_NUMBER_WORD = "|".join([*_UNITS, *_TENS, "hundred", "thousand", "and", "a"])
_NUMBER_START = "|".join([*_UNITS, *_TENS]) + r"|a(?=\s+(?:hundred|thousand))"
# "forty-five", "one hundred and twenty", "a hundred"
_SPELLED = rf"(?:{_NUMBER_START})(?:[\s-]+(?:{_NUMBER_WORD}))*"

_MONTHS = {
    name: number
    for number, name in enumerate(
        [
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
        ],
        start=1,
    )
}
_MONTH = "|".join([*_MONTHS, *(m[:3] for m in _MONTHS), "sept"])
_ORDINAL_WORDS = {
    "first": 1,
    "second": 2,
    "third": 3,
    "fourth": 4,
    "fifth": 5,
    "sixth": 6,
    "seventh": 7,
    "eighth": 8,
    "ninth": 9,
    "tenth": 10,
    "eleventh": 11,
    "twelfth": 12,
    "thirteenth": 13,
    "fourteenth": 14,
    "fifteenth": 15,
    "sixteenth": 16,
    "seventeenth": 17,
    "eighteenth": 18,
    "nineteenth": 19,
    "twentieth": 20,
    "thirtieth": 30,
}
_ORDINAL = (
    r"(?:\d{1,2}(?:st|nd|rd|th)?|(?:twenty|thirty)[\s-](?:"
    + "|".join(list(_ORDINAL_WORDS)[:9])
    + ")|"
    + "|".join(_ORDINAL_WORDS)
    + ")"
)
_SPOKEN_YEAR = (
    r"(?:two thousand(?:\s+and)?(?:\s+(?:[a-z]+(?:-[a-z]+)?))?"
    r"|(?:nineteen|eighteen) hundred(?:\s+and)?(?:\s+[a-z]+(?:[\s-][a-z]+)?)?"
    r"|(?:nineteen|twenty)\s+(?:[a-z]+(?:-[a-z]+)?))"
)
_ANNOTATION = re.compile(r" \(\d{4}-\d{2}-\d{2}\)")
_WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


# ---------------------------------------------------------------- digits


def _digits_from(spoken: str) -> str:
    out, repeat = [], 1
    for token in re.findall(r"[a-z]+|\d", spoken.lower()):
        if token in _REPEATS:
            repeat = _REPEATS[token]
            continue
        digit = _DIGIT_WORDS.get(token, token)
        out.append(digit * repeat)
        repeat = 1
    return "".join(out)


def normalise_digits(text: str) -> str:
    """'seven two oh six' -> '7206', 'double oh four one' -> '0041', '5 8 3 3' -> '5833',
    and digit groups split by pauses into one eight-digit customer number."""

    def code(match: re.Match) -> str:
        digits = _digits_from(match.group(0))
        return digits if len(digits) >= MIN_CODE_DIGITS else match.group(0)

    def customer_number(match: re.Match) -> str:
        if _NUMERIC_DATE.fullmatch(match.group(0)):
            return match.group(0)
        digits = re.sub(r"\D", "", match.group(0))
        return digits if len(digits) == CUSTOMER_NUMBER_DIGITS else match.group(0)

    text = _SPOKEN_DIGITS.sub(code, text)
    return _DIGIT_GROUPS.sub(customer_number, text)


# ---------------------------------------------------------------- money


def words_to_number(words: str) -> int | None:
    """'one hundred and twenty' -> 120, 'forty-five' -> 45, 'a hundred' -> 100."""
    total, current, seen = 0, 0, False
    for word in re.split(r"[\s-]+", words.lower().strip()):
        if word in ("and", ""):
            continue
        if word == "a":
            current = max(current, 1)
            continue
        if word in _UNITS:
            current += _UNITS[word]
        elif word in _TENS:
            current += _TENS[word]
        elif word == "hundred":
            current = max(current, 1) * 100
        elif word == "thousand":
            total += max(current, 1) * 1000
            current = 0
        else:
            return None
        seen = True
    return total + current if seen else None


def _euro(whole: str, cents: str | None = None) -> str:
    if cents:
        return f"€{int(whole)}.{int(cents):02d}"
    return f"€{int(whole)}"


# Parakeet sometimes writes "cent" as "sent", and a pause after "euro" as a full stop:
# "It was 34 euro. And 60 sent last Tuesday."
_CENT = r"(?:cents?|sent)"


def normalise_money(text: str) -> str:
    """'34 euro 60' -> '€34.60', '9 euro and 99 cent' -> '€9.99', 'forty-five euro' -> '€45'."""

    def spelled(match: re.Match) -> str:
        value = words_to_number(match.group(1))
        return match.group(0) if value is None else f"{value} {match.group(2)}"

    # Spelled-out amounts first: "forty-five euro" -> "45 euro", then spelled cents after a
    # figure: "12 euro ninety-nine" -> "12 euro 99".
    text = re.sub(rf"\b({_SPELLED})\s+(euros?|cents?)\b", spelled, text, flags=re.I)

    def spelled_cents(match: re.Match) -> str:
        cents = words_to_number(match.group(2))
        if cents is None or cents >= 100:
            return match.group(0)
        return _euro(match.group(1), str(cents))

    text = re.sub(
        rf"\b(\d+)\s*euros?[.,]?\s+(?:and\s+)?({_SPELLED})(?:\s+{_CENT})?\b",
        spelled_cents,
        text,
        flags=re.I,
    )
    text = re.sub(
        rf"\b(\d+)\s*euros?[.,]?\s+and\s+(\d{{1,2}})\s*{_CENT}\b",
        lambda m: _euro(m[1], m[2]),
        text,
        flags=re.I,
    )
    # The same with the euro sign Parakeet sometimes writes instead: "€34. And 60 sent".
    text = re.sub(
        rf"€(\d+)[.,]?\s+and\s+(\d{{1,2}}|{_SPELLED})\s*{_CENT}\b",
        lambda m: _euro(m[1], m[2] if m[2].isdigit() else str(words_to_number(m[2]) or "")),
        text,
        flags=re.I,
    )
    text = re.sub(
        r"\b(\d+)\s*euros?\s+(\d{1,2})\b(?!\s*(?:st|nd|rd|th|cent|euro))",
        lambda m: _euro(m[1], m[2]),
        text,
        flags=re.I,
    )
    text = re.sub(r"\b(\d+)\.(\d{2})\s*euros?\b", lambda m: _euro(m[1], m[2]), text, flags=re.I)
    return re.sub(r"\b(\d+)\s*euros?\b", lambda m: _euro(m[1]), text, flags=re.I)


# ---------------------------------------------------------------- dates


def _ordinal_value(token: str) -> int | None:
    token = token.lower().replace("-", " ")
    digits = re.match(r"(\d{1,2})", token)
    if digits:
        return int(digits.group(1))
    if token in _ORDINAL_WORDS:
        return _ORDINAL_WORDS[token]
    parts = token.split()
    if len(parts) == 2 and parts[0] in _TENS and parts[1] in _ORDINAL_WORDS:
        return _TENS[parts[0]] + _ORDINAL_WORDS[parts[1]]
    return None


def _month_value(token: str) -> int:
    token = token.lower()[:3]
    return next(number for name, number in _MONTHS.items() if name.startswith(token))


def spoken_year(words: str) -> int | None:
    """'nineteen ninety-one' -> 1991, 'two thousand and one' -> 2001, 'twenty twenty' -> 2020."""
    words = words.lower().strip()
    if words.startswith("two thousand"):
        rest = words.removeprefix("two thousand").strip()
        return 2000 + (words_to_number(rest) or 0) if rest else 2000
    hundred = re.fullmatch(r"(nineteen|eighteen) hundred(?:\s+and)?(?:\s+(.+))?", words)
    if hundred:
        century = words_to_number(hundred.group(1))
        rest = words_to_number(hundred.group(2)) if hundred.group(2) else 0
        return None if rest is None or rest >= 100 else century * 100 + rest
    parts = re.split(r"\s+", words, maxsplit=1)
    if len(parts) == 2:
        century, decade = words_to_number(parts[0]), words_to_number(parts[1])
        if century in (19, 20) and decade is not None and decade < 100:
            return century * 100 + decade
    return None


def _year_value(token: str | None, month: int, day: int, today: date) -> int | None:
    if token and not token.isdigit():
        return spoken_year(token)
    if token:
        year = int(token)
        if year < 100:  # '85 or 85: the most recent year that isn't in the future
            year += 2000 if 2000 + year <= today.year else 1900
        return year
    # No year: this year, unless that would be in the future.
    try:
        this_year = date(today.year, month, day)
    except ValueError:
        return None
    return today.year if this_year <= today else today.year - 1


def _iso(year: int | None, month: int, day: int) -> str | None:
    if year is None:
        return None
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def _annotate(text: str, pattern: re.Pattern, resolve) -> str:
    """Append ' (YYYY-MM-DD)' after each match that resolves to a date."""

    def replace(match: re.Match) -> str:
        if _ANNOTATION.match(text, match.end()) or "(" in match.group(0):
            return match.group(0)
        value = resolve(match)
        return f"{match.group(0)} ({value})" if value else match.group(0)

    return pattern.sub(replace, text)


def annotate_dates(text: str, today: date) -> str:
    """Follow each date the caller mentions with the exact date it means, in ISO form."""
    # 14/07/1985, 14-07-85, 14.07.1985: day first, as written in Ireland and the UK.
    numeric = re.compile(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](\d{2}|\d{4})\b")
    text = _annotate(
        text,
        numeric,
        lambda m: _iso(_year_value(m[3], int(m[2]), int(m[1]), today), int(m[2]), int(m[1])),
    )

    # the 21st of November 1978, 21 November 1978, the ninth of June, 3rd of March '91.
    day_month = re.compile(
        rf"\b(?:the\s+)?({_ORDINAL})\s+(?:of\s+)?({_MONTH})\b"
        rf"(?:[.,]?\s+'?(\d{{4}}|\d{{2}}|{_SPOKEN_YEAR})\b)?",
        re.I,
    )

    def resolve_day_month(m: re.Match) -> str | None:
        day, month = _ordinal_value(m[1]), _month_value(m[2])
        if day is None:
            return None
        return _iso(_year_value(m[3], month, day, today), month, day)

    text = _annotate(text, day_month, resolve_day_month)

    # November the 21st 1978, March 3rd.
    month_day = re.compile(
        rf"\b({_MONTH})\s+(?:the\s+)?({_ORDINAL})\b(?:,?\s+(\d{{4}})\b)?(?!\s+of\b)", re.I
    )

    def resolve_month_day(m: re.Match) -> str | None:
        day, month = _ordinal_value(m[2]), _month_value(m[1])
        if day is None:
            return None
        return _iso(_year_value(m[3], month, day, today), month, day)

    text = _annotate(text, month_day, resolve_month_day)

    # "on the 3rd" with no month: this month, unless that's still to come.
    bare_ordinal = re.compile(
        rf"\b(?:on\s+the\s+({_ORDINAL})\b(?!\s+(?:of\b|{_MONTH}))"
        rf"|the\s+({_ORDINAL})(?=\s*(?:[.,;!?]|$)))",
        re.I,
    )

    def resolve_bare(m: re.Match) -> str | None:
        day = _ordinal_value(m[1] or m[2])
        if day is None or not 1 <= day <= 31:
            return None
        year, month = today.year, today.month
        if day > today.day:
            month -= 1
            if month == 0:
                year, month = year - 1, 12
        return _iso(year, month, day)

    text = _annotate(text, bare_ordinal, resolve_bare)

    relative = {
        "the day before yesterday": today - timedelta(days=2),
        "yesterday": today - timedelta(days=1),
        "last night": today - timedelta(days=1),
        "this morning": today,
        "today": today,
        "a week ago": today - timedelta(days=7),
    }
    for phrase, value in relative.items():
        text = _annotate(
            text,
            re.compile(rf"\b{phrase}\b(?! \(2)", re.I),
            lambda m, value=value: value.isoformat(),
        )
    text = _annotate(
        text,
        re.compile(r"\b(\d+|two|three|four|five|six)\s+days\s+ago\b", re.I),
        lambda m: (
            today - timedelta(days=int(m[1]) if m[1].isdigit() else _UNITS[m[1].lower()])
        ).isoformat(),
    )

    # Weekdays mean the most recent one before today: "on Saturday", "last Tuesday".
    weekday = re.compile(rf"\b(?:(?:on|last|this past)\s+)?({'|'.join(_WEEKDAYS)})\b", re.I)

    def resolve_weekday(m: re.Match) -> str:
        back = (today.weekday() - _WEEKDAYS.index(m[1].lower())) % 7 or 7
        return (today - timedelta(days=back)).isoformat()

    return _annotate(text, weekday, resolve_weekday)


def understand(text: str, today: date) -> str:
    """The caller's words with digits, amounts and dates made exact (see the module docs)."""
    return annotate_dates(normalise_money(normalise_digits(text)), today)
