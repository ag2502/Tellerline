"""Head-to-head: single prompt vs intent router, on single-turn cases and multi-turn dialogues.

Each conversation starts after the greeting (and, for verified callers, after verification).
Every caller turn goes through a brain (``tellerline.brain``): it plans the prompt, the LLM
answers with a reply or an ACTION line, actions are "run" against mock results and spoken
from templates, and the brain records what the caller heard. Each turn is scored like the
single-turn benchmark; a dialogue succeeds only if every turn is right.

Latency per turn is routing time (router only) plus LLM time to the first spoken sentence,
or to the complete action line.

Usage:
    python -m bench.dialogues --split dev --models e2b e4b --brains single router
"""

import argparse
import json
from collections import defaultdict
from typing import Any

from openai import OpenAI

from bench.common import DATA_DIR, RESULTS_DIR, ResultWriter, ms, summarize
from bench.llm import (
    BENCH_TODAY,
    MOCK_TOOL_RESULTS,
    SPLITS,
    VERIFIED_HISTORY,
    load_cases,
    start_server,
    stream_completion,
)
from bench.scoring import score_case
from tellerline.banking.responses import respond
from tellerline.brain import RouterBrain, SinglePromptBrain, opening_history
from tellerline.config import LLM_MODELS, LLM_SERVER_HOST, LLM_SERVER_PORT
from tellerline.router.classifier import IntentClassifier
from tellerline.router.embedder import Embedder
from tellerline.router.intents import EXAMPLES

BRAINS = ("single", "router")


def conversations(split: str) -> list[dict[str, Any]]:
    """Single-turn cases as one-turn conversations, then the multi-turn dialogues."""
    found = [
        {
            "id": case["id"],
            "kind": "single",
            "verified": case["history"] == "verified",
            "turns": [case],
        }
        for case in load_cases(split)
    ]
    for line in (DATA_DIR / f"dialogues_{split}.jsonl").read_text().splitlines():
        dialogue = json.loads(line)
        found.append({**dialogue, "kind": "multi"})
    return found


def make_brain(kind: str, verified: bool, classifier: IntentClassifier | None):
    history = VERIFIED_HISTORY["actions"] if verified else opening_history()
    if kind == "router":
        return RouterBrain(classifier, BENCH_TODAY, verified, history)
    return SinglePromptBrain(BENCH_TODAY, verified, history)


def run_conversation(client: OpenAI, model_id: str, brain, conversation: dict) -> list[dict]:
    records = []
    for index, turn in enumerate(conversation["turns"]):
        plan = brain.plan(turn["user"])
        result = stream_completion(client, model_id, plan.messages, stop=["\n"])
        # The same step the live agent uses: run the action, or say a follow-up question (a
        # missing value) or a fallback (an action the caller can't have yet) instead.
        outcome = brain.interpret(plan, result["text"])
        action, question = outcome.action, outcome.say
        operation = action.tool if action else None
        arguments = action.arguments if action else {}
        score = score_case(turn, operation, arguments)
        if question:
            spoken = question
            llm_s = result["total_s"]
        elif action:
            try:
                spoken = respond(operation, arguments, MOCK_TOOL_RESULTS[operation], BENCH_TODAY)
            except (KeyError, TypeError, ValueError):
                spoken = "Sorry, something went wrong there."
            llm_s = result["total_s"]
        else:
            spoken = result["text"].strip()
            llm_s = (
                result["first_sentence_s"]
                if result["first_sentence_s"] is not None
                else result["total_s"]
            )
        brain.record(turn["user"], plan, action, spoken)
        records.append(
            {
                "conversation": conversation["id"],
                "kind": conversation["kind"],
                "turn": index,
                "user": turn["user"],
                "understood": plan.text,
                "step": plan.step,
                "route_reason": plan.route_reason,
                "intent": plan.intent,
                "intent_score": plan.intent_score,
                "text": result["text"],
                "clarifying_question": question,
                "operation": operation,
                "arguments": arguments,
                "spoken": spoken,
                "ok": score["ok"],
                "expected": turn["expect"],
                "route_s": plan.route_s,
                "llm_s": llm_s,
                "decision_s": plan.route_s + llm_s,
                "action": action is not None,
                "prompt_tokens": result["prompt_tokens"],
                "cached_tokens": result["cached_tokens"],
            }
        )
    return records


def summarise(records: list[dict]) -> dict[str, Any]:
    single = [r for r in records if r["kind"] == "single"]
    multi = [r for r in records if r["kind"] == "multi"]
    by_dialogue = defaultdict(list)
    for r in multi:
        by_dialogue[r["conversation"]].append(r["ok"])
    return {
        "single_turn_accuracy": sum(r["ok"] for r in single) / len(single) if single else None,
        "dialogue_turn_accuracy": sum(r["ok"] for r in multi) / len(multi) if multi else None,
        "dialogue_success": (
            sum(all(v) for v in by_dialogue.values()) / len(by_dialogue) if by_dialogue else None
        ),
        "overall_turn_accuracy": sum(r["ok"] for r in records) / len(records),
        "latency_s": {
            "decision_reply": summarize([r["decision_s"] for r in records if not r["action"]]),
            "decision_action": summarize([r["decision_s"] for r in records if r["action"]]),
            "route": summarize([r["route_s"] for r in records]),
        },
        "failures": [
            {k: r[k] for k in ("conversation", "turn", "user", "step", "text", "expected")}
            for r in records
            if not r["ok"]
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--models", nargs="+", default=list(LLM_MODELS), choices=list(LLM_MODELS))
    parser.add_argument("--brains", nargs="+", default=list(BRAINS), choices=BRAINS)
    parser.add_argument("--split", choices=SPLITS, default="test")
    parser.add_argument("--repeats", type=int, default=1)
    parser.add_argument("--port", type=int, default=LLM_SERVER_PORT)
    args = parser.parse_args()

    classifier = IntentClassifier(Embedder(), EXAMPLES) if "router" in args.brains else None
    convs = conversations(args.split)
    warmup = conversations("test" if args.split == "dev" else "dev")
    (RESULTS_DIR / "logs").mkdir(parents=True, exist_ok=True)

    with ResultWriter("dialogues", vars(args)) as writer:
        for key in args.models:
            model_id = LLM_MODELS[key]
            server = start_server(
                model_id, args.port, RESULTS_DIR / "logs" / f"mlx-server-{key}.log"
            )
            try:
                client = OpenAI(
                    base_url=f"http://{LLM_SERVER_HOST}:{args.port}/v1",
                    api_key="not-needed",
                    timeout=120,
                )
                for brain_kind in args.brains:
                    # Warm every prompt this brain uses (a long-running server has them all
                    # cached) with the other split's conversations; those results are discarded.
                    for conversation in warmup:
                        run_conversation(
                            client,
                            model_id,
                            make_brain(brain_kind, conversation["verified"], classifier),
                            conversation,
                        )
                    records = []
                    for repeat in range(args.repeats):
                        for conversation in convs:
                            brain = make_brain(brain_kind, conversation["verified"], classifier)
                            for record in run_conversation(client, model_id, brain, conversation):
                                record.update(model=key, brain=brain_kind, repeat=repeat)
                                writer.sample(**record)
                                records.append(record)
                    summary = {"model": key, "brain": brain_kind, **summarise(records)}
                    writer.summary(**summary)
                    lat = summary["latency_s"]
                    print(
                        f"{key} {brain_kind:<6} "
                        f"single-turn {summary['single_turn_accuracy']:.0%} | "
                        f"dialogue turns {summary['dialogue_turn_accuracy']:.0%} | "
                        f"dialogues fully right {summary['dialogue_success']:.0%} | "
                        f"reply p90 {ms(lat['decision_reply']['p90'])} ms | "
                        f"action p90 {ms(lat['decision_action']['p90'])} ms | "
                        f"routing p90 {ms(lat['route']['p90'])} ms"
                    )
                    for failure in summary["failures"]:
                        print(
                            f"   FAIL {failure['conversation']}#{failure['turn']} "
                            f"[{failure['step']}] "
                            f"{failure['user'][:45]!r} -> {failure['text'][:60]!r} "
                            f"(expected {failure['expected'].get('tool')})"
                        )
            finally:
                server.terminate()
                server.wait(timeout=30)
    print(f"Results: {writer.path}")


if __name__ == "__main__":
    main()
