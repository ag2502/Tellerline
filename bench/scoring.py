"""Score an LLM tool call against the expected call for a benchmark case."""

from typing import Any

AMOUNT_TOLERANCE = 0.005


def _compact(value: Any) -> str:
    return "".join(str(value).split()).casefold()


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(_compact(value).lstrip("€").replace(",", ""))
        except ValueError:
            return None
    return None


def values_match(expected: Any, actual: Any) -> bool:
    """Compare one argument value.

    Numbers compare numerically (so 5, 5.0 and "5" match). Strings compare ignoring case and
    whitespace but keep leading zeros, so card digits "0093" do not match 93.
    """
    if isinstance(expected, int | float) and not isinstance(expected, bool):
        number = _as_float(actual)
        return number is not None and abs(float(expected) - number) <= AMOUNT_TOLERANCE
    if isinstance(expected, str) and isinstance(actual, str | int | float):
        return _compact(expected) == _compact(actual)
    return expected == actual


def score_case(case: dict[str, Any], tool_name: str | None, arguments: dict[str, Any]) -> dict:
    """Return whether the right tool (or no tool) was called with the expected arguments.

    A case's ``expect`` names the preferred tool (``None`` for a spoken reply only) and the
    arguments that must match. ``accept`` lists alternative tools, or ``None`` for no tool,
    that also count as correct; their arguments are not checked.
    """
    expect = case["expect"]

    if tool_name == expect.get("tool"):
        missing = [key for key in expect.get("args", {}) if key not in arguments]
        wrong = [
            key
            for key, value in expect.get("args", {}).items()
            if key in arguments and not values_match(value, arguments[key])
        ]
        ok = not missing and not wrong
        return {"tool_ok": True, "ok": ok, "missing_args": missing, "wrong_args": wrong}

    ok = tool_name in case.get("accept", [])
    return {"tool_ok": ok, "ok": ok, "missing_args": [], "wrong_args": []}
