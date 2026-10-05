"""Benchmark Gemma 4 on mlx-lm's OpenAI-compatible server: action accuracy and latency.

For each model this starts ``mlx_lm.server``, runs every case in ``data/tool_cases_<split>.jsonl``
through the real system prompt for that step of the call, and records:

- time to first token,
- time to the first complete sentence of a spoken reply (when TTS could start),
- for actions: time until the action is complete. The agent speaks results from templates, so
  that is when the answer is ready for TTS.

Two modes (see ``tellerline.prompts``):

- ``actions`` (default): prompt only; the model writes an ``ACTION`` line that code parses.
- ``tools``: native function calling. ``--tool-call-bias`` boosts the tool-call token, and
  ``--llm-follow-up`` also times a second LLM pass that speaks a mock result.

Usage:
    python -m bench.llm --models e2b e4b --repeats 3                # held-out test set
    python -m bench.llm --split dev --models e4b --repeats 1          # tuning
    python -m bench.llm --mode tools --tool-call-bias 0 6 --split dev # tool-calling comparison
    python -m bench.llm --base-url http://127.0.0.1:8080/v1 --models e4b   # server already running
"""

import argparse
import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from huggingface_hub import snapshot_download
from mlx_lm.tokenizer_utils import load as load_tokenizer
from openai import OpenAI

from bench.common import (
    DATA_DIR,
    RESULTS_DIR,
    ResultWriter,
    has_clause_end,
    has_sentence_end,
    ms,
    now,
    summarize,
)
from bench.scoring import score_case
from tellerline.actions import NODE_ACTIONS, parse_action
from tellerline.banking.responses import respond
from tellerline.banking.tools import tools_for
from tellerline.config import LLM_MODELS, LLM_SERVER_HOST, LLM_SERVER_PORT
from tellerline.llm_server import MAX_TOKENS, start_server
from tellerline.prompts import MODES, build_system_prompt

BENCH_TODAY = date(2026, 9, 14)

GREETING = (
    "Hello, you're through to Tellerline Bank. I'm an AI assistant. How can I help you today?"
)
GREETING_HISTORY = [
    {"role": "user", "content": "Hello?"},
    {"role": "assistant", "content": GREETING},
]
_DETAILS = {
    "role": "user",
    "content": "I need some help with my account. My customer number is 45127890 and I was born "
    "on 3 March 1991.",
}
_VERIFIED_REPLY = {
    "role": "assistant",
    "content": "Thanks, Aoife, you're verified. What can I help you with?",
}
# A verified call's context holds the verification exchange as the agent would have recorded it.
VERIFIED_HISTORY = {
    # The agent records what the caller heard; the ACTION line itself stays out of the context.
    "actions": [*GREETING_HISTORY, _DETAILS, _VERIFIED_REPLY],
    "tools": [
        *GREETING_HISTORY,
        _DETAILS,
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": "call_verify",
                    "type": "function",
                    "function": {
                        "name": "verify_identity",
                        "arguments": json.dumps(
                            {"customer_number": "45127890", "date_of_birth": "1991-03-03"}
                        ),
                    },
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": "call_verify",
            "content": json.dumps({"verified": True, "first_name": "Aoife"}),
        },
        _VERIFIED_REPLY,
    ],
}
HISTORY_KINDS = ("greeting", "verified")
# The step of the call each history belongs to (see tellerline.prompts.NODE_TASKS).
NODES = {"greeting": "identify", "verified": "assist"}

MOCK_TOOL_RESULTS: dict[str, dict[str, Any]] = {
    "verify_identity": {"verified": True, "first_name": "Aoife"},
    "get_balance": {"balance_eur": 1250.40, "available_eur": 1180.40},
    "get_recent_transactions": {
        "transactions": [
            {"date": "2026-09-12", "merchant": "Tesco Rathmines", "amount_eur": -42.17},
            {"date": "2026-09-11", "merchant": "Salary, Acme Ltd", "amount_eur": 2650.00},
            {"date": "2026-09-10", "merchant": "Dublin Bus", "amount_eur": -2.00},
        ]
    },
    "freeze_card": {"status": "frozen"},
    "unfreeze_card": {"status": "active"},
    "get_card_status": {
        "status": "frozen",
        "freeze_reason": "lost",
        "replacement_ordered_on": "2026-09-11",
        "replacement_arrives_by": "2026-09-18",
    },
    "order_replacement_card": {"status": "ordered", "arrives_in_working_days": 5},
    "dispute_transaction": {"status": "opened", "case_reference": "DSP-20417"},
    "transfer_to_human": {"status": "queued", "estimated_wait_minutes": 3},
    "end_call": {"status": "ending"},
}


SPLITS = ("dev", "test")


def load_cases(split: str = "test") -> list[dict[str, Any]]:
    """``dev`` cases are for tuning prompts; ``test`` cases are held out for reported results."""
    path = DATA_DIR / f"tool_cases_{split}.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def history(kind: str, mode: str) -> list[dict[str, Any]]:
    return GREETING_HISTORY if kind == "greeting" else VERIFIED_HISTORY[mode]


def build_messages(case: dict[str, Any], mode: str = "actions") -> list[dict[str, Any]]:
    node = NODES[case["history"]]
    messages = [{"role": "system", "content": build_system_prompt(BENCH_TODAY, node, mode)}]
    messages.extend(history(case["history"], mode))
    messages.append({"role": "user", "content": case["user"]})
    return messages


def stream_completion(
    client: OpenAI,
    model: str,
    messages: list[dict[str, Any]],
    tools: list[dict] | None = None,
    logit_bias: dict[int, float] | None = None,
    stop: list[str] | None = None,
) -> dict:
    """Stream one chat completion and time the moments that matter for speech."""
    start = now()
    first_token = first_clause = first_sentence = None
    text = ""
    tool_calls: list[dict[str, str]] = []
    usage = None

    stream = client.chat.completions.create(
        model=model,
        messages=messages,
        stream=True,
        temperature=0.0,
        max_tokens=MAX_TOKENS,
        stream_options={"include_usage": True},
        **({"tools": tools} if tools else {}),
        **({"logit_bias": logit_bias} if logit_bias else {}),
        **({"stop": stop} if stop else {}),
    )
    for chunk in stream:
        if chunk.usage:
            usage = chunk.usage
        if not chunk.choices:
            continue
        delta = chunk.choices[0].delta
        received = False
        if delta.content:
            text += delta.content
            received = True
        for call in delta.tool_calls or []:
            if call.function and call.function.name:
                tool_calls.append({"name": call.function.name, "arguments": ""})
            if call.function and call.function.arguments and tool_calls:
                tool_calls[-1]["arguments"] += call.function.arguments
            received = True
        elapsed = now() - start
        if received and first_token is None:
            first_token = elapsed
        if first_clause is None and has_clause_end(text):
            first_clause = elapsed
        if first_sentence is None and has_sentence_end(text):
            first_sentence = elapsed

    total = now() - start
    if text.strip():
        first_clause = first_clause if first_clause is not None else total
        first_sentence = first_sentence if first_sentence is not None else total

    cached = None
    if usage and getattr(usage, "prompt_tokens_details", None):
        cached = getattr(usage.prompt_tokens_details, "cached_tokens", None)
    return {
        "text": text,
        "tool_calls": tool_calls,
        "ttft_s": first_token,
        "first_clause_s": first_clause,
        "first_sentence_s": first_sentence,
        "total_s": total,
        "prompt_tokens": usage.prompt_tokens if usage else None,
        "cached_tokens": cached,
        "completion_tokens": usage.completion_tokens if usage else None,
    }


def follow_up_messages(messages: list[dict[str, Any]], call: dict[str, str]) -> list[dict]:
    """Conversation after the tool ran: the assistant's call plus a mock result."""
    call_id = "call_0"
    return [
        *messages,
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {
                    "id": call_id,
                    "type": "function",
                    "function": {"name": call["name"], "arguments": call["arguments"] or "{}"},
                }
            ],
        },
        {
            "role": "tool",
            "tool_call_id": call_id,
            "content": json.dumps(MOCK_TOOL_RESULTS.get(call["name"], {"status": "ok"})),
        },
    ]


def tool_call_token_id(model_id: str) -> int:
    """The token that opens a tool call, e.g. Gemma 4's ``<|tool_call>``."""
    tokenizer = load_tokenizer(Path(snapshot_download(model_id)))
    (token,) = tokenizer.tool_call_start_tokens
    return token


def run_case(
    client: OpenAI,
    model_id: str,
    case: dict[str, Any],
    mode: str,
    bias: dict[int, float] | None,
) -> tuple[dict, str | None, dict[str, Any], list[dict], list[dict] | None]:
    """One request for one case: the raw result, the chosen operation and its arguments."""
    node = NODES[case["history"]]
    messages = build_messages(case, mode)
    if mode == "actions":
        # An action is a single line, so generation can stop at the first newline.
        result = stream_completion(client, model_id, messages, stop=["\n"])
        action = parse_action(result["text"], NODE_ACTIONS[node])
        if action and not action.complete:
            action = None  # the agent asks a follow-up question instead
        return (
            result,
            action.tool if action else None,
            action.arguments if action else {},
            messages,
            None,
        )

    tools = tools_for(node)
    result = stream_completion(client, model_id, messages, tools, bias)
    call = result["tool_calls"][0] if result["tool_calls"] else None
    arguments: dict[str, Any] = {}
    if call:
        try:
            arguments = json.loads(call["arguments"] or "{}")
        except json.JSONDecodeError:
            arguments = {}
    return result, call["name"] if call else None, arguments, messages, tools


def bench_model(
    key: str,
    model_id: str,
    base_url: str,
    repeats: int,
    cases: list[dict],
    writer: ResultWriter,
    mode: str = "actions",
    llm_follow_up: bool = False,
    tool_call_bias: float = 0.0,
) -> dict[str, Any]:
    """Run every case against one model.

    In ``tools`` mode, ``tool_call_bias`` is added to the logit of the tool-call start token.
    Small models often announce an action ("I can freeze that for you") when a tool call was
    nearly as likely; a modest bias tips those decisions without forcing a call.
    """
    client = OpenAI(base_url=base_url, api_key="not-needed", max_retries=0, timeout=120)
    bias = None
    if mode == "tools" and tool_call_bias:
        bias = {tool_call_token_id(model_id): tool_call_bias}
    label = {
        "model": key,
        "mode": mode,
        "tool_call_bias": tool_call_bias if mode == "tools" else None,
    }

    # The first request fills the prompt cache with the system prompt.
    cold, *_ = run_case(client, model_id, cases[0], mode, bias)
    writer.sample(**label, kind="cold", case="cold-start", **cold)
    print(f"  cold start: first token {ms(cold['ttft_s'] or cold['total_s'])} ms")

    latencies: dict[str, list[float]] = defaultdict(list)
    correct: dict[str, list[bool]] = defaultdict(list)
    failures = []

    for repeat in range(repeats):
        for case in cases:
            result, operation, arguments, messages, tools = run_case(
                client, model_id, case, mode, bias
            )
            score = score_case(case, operation, arguments)

            follow_up = None
            spoken = None
            if operation:
                # Results are spoken from templates, so the answer is ready once the action is.
                latencies["action_complete_s"].append(result["total_s"])
                try:
                    spoken = respond(
                        operation, arguments, MOCK_TOOL_RESULTS[operation], BENCH_TODAY
                    )
                except (KeyError, TypeError, ValueError) as error:
                    spoken = f"<template error: {type(error).__name__}: {error}>"
                if llm_follow_up and mode == "tools":
                    call = result["tool_calls"][0]
                    follow_up = stream_completion(
                        client, model_id, follow_up_messages(messages, call), tools, bias
                    )
                    if follow_up["first_sentence_s"] is not None:
                        latencies["tool_turn_llm_follow_up_s"].append(
                            result["total_s"] + follow_up["first_sentence_s"]
                        )
            elif result["first_sentence_s"] is not None:
                latencies["reply_first_sentence_s"].append(result["first_sentence_s"])
                latencies["reply_first_clause_s"].append(result["first_clause_s"])
            if result["ttft_s"] is not None:
                latencies["ttft_s"].append(result["ttft_s"])

            if repeat == 0:
                correct["all"].append(score["ok"])
                correct[case["category"]].append(score["ok"])
                if not score["ok"]:
                    failures.append(
                        {
                            "case": case["id"],
                            "expected": case["expect"],
                            "got_tool": operation,
                            "got_args": arguments,
                            "reply": result["text"][:200],
                        }
                    )
            writer.sample(
                **label,
                kind="case",
                case=case["id"],
                category=case["category"],
                repeat=repeat,
                score=score,
                operation=operation,
                arguments=arguments,
                **result,
                spoken=spoken,
                follow_up=follow_up,
            )
        print(f"  repeat {repeat + 1}/{repeats} done")

    accuracy = {name: sum(values) / len(values) for name, values in correct.items()}
    summary = {
        **label,
        "model_id": model_id,
        "accuracy": accuracy,
        "latency": {name: summarize(values) for name, values in latencies.items()},
        "cold_ttft_s": cold["ttft_s"],
        "failures": failures,
    }
    writer.summary(**summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--models", nargs="+", default=list(LLM_MODELS), choices=list(LLM_MODELS))
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--port", type=int, default=LLM_SERVER_PORT)
    parser.add_argument("--base-url", help="Use an already running server instead of starting one.")
    parser.add_argument("--split", choices=SPLITS, default="test")
    parser.add_argument("--mode", choices=MODES, default="actions")
    parser.add_argument(
        "--tool-call-bias",
        nargs="+",
        type=float,
        default=[0.0],
        help="Logit bias for the tool-call start token; several values run a sweep.",
    )
    parser.add_argument(
        "--llm-follow-up",
        action="store_true",
        help="Also time a second LLM pass that speaks each tool result, the design that "
        "response templates replace.",
    )
    args = parser.parse_args()

    cases = load_cases(args.split)
    config = {
        "models": args.models,
        "repeats": args.repeats,
        "split": args.split,
        "mode": args.mode,
        "cases": len(cases),
        "llm_follow_up": args.llm_follow_up,
        "tool_call_bias": args.tool_call_bias,
        "today": str(BENCH_TODAY),
    }
    (RESULTS_DIR / "logs").mkdir(parents=True, exist_ok=True)

    with ResultWriter("llm", config) as writer:
        for key in args.models:
            model_id = LLM_MODELS[key]
            print(f"\n{key}: {model_id}")
            server = None
            if not args.base_url:
                server = start_server(
                    model_id, args.port, RESULTS_DIR / "logs" / f"mlx-server-{key}.log"
                )
            try:
                base_url = args.base_url or f"http://{LLM_SERVER_HOST}:{args.port}/v1"
                biases = args.tool_call_bias if args.mode == "tools" else [0.0]
                for bias in biases:
                    if args.mode == "tools":
                        print(f" tool-call bias {bias:g}")
                    summary = bench_model(
                        key,
                        model_id,
                        base_url,
                        args.repeats,
                        cases,
                        writer,
                        args.mode,
                        args.llm_follow_up,
                        bias,
                    )
                    print_summary(summary)
            finally:
                if server:
                    server.terminate()
                    server.wait(timeout=30)
        print(f"\nResults: {writer.path}")


def print_summary(summary: dict[str, Any]) -> None:
    lat = summary["latency"]
    print(f"  accuracy: {summary['accuracy']['all']:.0%}")
    names = (
        "ttft_s",
        "reply_first_sentence_s",
        "tool_call_complete_s",
        "tool_turn_llm_follow_up_s",
    )
    for name in names:
        if lat.get(name, {}).get("n"):
            print(f"  {name}: p50 {ms(lat[name]['p50'])} ms, p90 {ms(lat[name]['p90'])} ms")


if __name__ == "__main__":
    main()
