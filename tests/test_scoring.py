from bench.scoring import score_case, values_match

FREEZE = {
    "expect": {"tool": "freeze_card", "args": {"card_last_four": "0093", "reason": "lost"}},
}


def test_numbers_match_across_types():
    assert values_match(5, "5")
    assert values_match(49.99, "49.99")
    assert values_match(120, "€120")
    assert not values_match(49.99, 49.9)


def test_strings_ignore_case_and_whitespace_but_keep_leading_zeros():
    assert values_match("45127890", "4512 7890")
    assert values_match("StreamFlix", "streamflix")
    assert not values_match("0093", 93)
    assert not values_match("0093", "93")


def test_correct_tool_and_arguments():
    result = score_case(FREEZE, "freeze_card", {"card_last_four": "0093", "reason": "LOST"})
    assert result["ok"]


def test_wrong_and_missing_arguments_are_reported():
    result = score_case(FREEZE, "freeze_card", {"card_last_four": "0039"})
    assert not result["ok"]
    assert result["tool_ok"]
    assert result["wrong_args"] == ["card_last_four"]
    assert result["missing_args"] == ["reason"]


def test_no_tool_expected():
    case = {"expect": {"tool": None}}
    assert score_case(case, None, {})["ok"]
    assert not score_case(case, "get_balance", {"account": "current"})["ok"]


def test_accepted_alternatives_skip_argument_checks():
    case = {"expect": {"tool": None}, "accept": ["transfer_to_human"]}
    assert score_case(case, "transfer_to_human", {})["ok"]
    case = {"expect": {"tool": "get_balance"}, "accept": [None]}
    assert score_case(case, None, {})["ok"]
