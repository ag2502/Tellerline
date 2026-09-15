import json
from datetime import date

import pytest

from bench.llm import HISTORY_KINDS, MOCK_TOOL_RESULTS, NODES, SPLITS, build_messages, load_cases
from tellerline.actions import NODE_ACTIONS, parse_action
from tellerline.banking.tools import NODE_TOOLS, TOOL_NAMES, TOOLS, tool_properties, tools_for
from tellerline.prompts import MODES, NODE_TASKS, build_system_prompt, date_context


def test_tool_schemas_are_well_formed():
    assert len(TOOL_NAMES) == len(TOOLS)
    for tool in TOOLS:
        parameters = tool["function"]["parameters"]
        assert parameters["type"] == "object"
        assert set(parameters["required"]) <= set(parameters["properties"])
    json.dumps(TOOLS)


def test_every_tool_has_a_mock_result():
    assert set(MOCK_TOOL_RESULTS) == TOOL_NAMES


@pytest.mark.parametrize("split", SPLITS)
def test_benchmark_cases_reference_real_tools_and_arguments(split):
    cases = load_cases(split)
    assert len({case["id"] for case in cases}) == len(cases)
    for case in cases:
        expected = case["expect"]["tool"]
        if expected is not None:
            assert expected in TOOL_NAMES, case["id"]
            assert set(case["expect"].get("args", {})) <= set(tool_properties(expected)), case["id"]
        for alternative in case.get("accept", []):
            assert alternative is None or alternative in TOOL_NAMES, case["id"]
        assert case["history"] in HISTORY_KINDS, case["id"]


def test_dev_and_test_cases_do_not_overlap():
    dev, test = load_cases("dev"), load_cases("test")
    assert not {c["id"] for c in dev} & {c["id"] for c in test}
    assert not {c["user"] for c in dev} & {c["user"] for c in test}


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("split", SPLITS)
def test_messages_alternate_and_end_with_the_caller(split, mode):
    for case in load_cases(split):
        roles = [message["role"] for message in build_messages(case, mode)]
        assert roles[0] == "system"
        assert roles[-1] == "user"
        assert all(a != b for a, b in zip(roles[1:], roles[2:], strict=False))


@pytest.mark.parametrize("mode", MODES)
@pytest.mark.parametrize("node", NODE_TASKS)
def test_system_prompt_ends_with_the_date(node, mode):
    prompt = build_system_prompt(date(2026, 9, 14), node, mode)
    assert "Today is Monday 14 September 2026" in prompt.splitlines()[-1]
    assert NODE_TASKS[node] in prompt
    assert ("ACTION" in prompt) == (mode == "actions")


def test_action_examples_parse_and_are_allowed_at_their_step():
    for node in NODE_TASKS:
        prompt = build_system_prompt(date(2026, 9, 14), node, "actions")
        examples = prompt.split("Examples (made-up callers):")[1]
        lines = [
            line.removeprefix("You: ") for line in examples.splitlines() if "You: ACTION" in line
        ]
        assert lines
        assert all(parse_action(line, NODE_ACTIONS[node]) for line in lines)


def test_examples_are_not_benchmark_cases():
    prompts = " ".join(build_system_prompt(date(2026, 9, 14), n, "actions") for n in NODE_TASKS)
    for split in SPLITS:
        for case in load_cases(split):
            assert case["user"] not in prompts


def test_nodes_only_offer_known_tools():
    assert set(NODE_TASKS) == set(NODE_TOOLS) == set(NODES.values())
    for node, names in NODE_TOOLS.items():
        assert {t["function"]["name"] for t in tools_for(node)} == set(names) <= TOOL_NAMES


def test_banking_tools_are_unavailable_before_verification():
    identify = {t["function"]["name"] for t in tools_for("identify")}
    assert identify.isdisjoint({"get_balance", "freeze_card", "dispute_transaction"})


def test_date_context_lists_the_past_week():
    text = date_context(date(2026, 9, 14))
    assert text.startswith("Today is Monday 14 September 2026 (2026-09-14).")
    assert "Yesterday Sunday 13 September was 2026-09-13." in text
    assert "Saturday 12 September was 2026-09-12." in text
    assert "Last Monday 7 September was 2026-09-07." in text
