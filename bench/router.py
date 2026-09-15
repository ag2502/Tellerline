"""Benchmark the intent classifier: accuracy, confidence thresholds and CPU latency.

Every single-turn case and every dialogue turn carries the intent(s) that count as correct.
Thresholds are swept on the dev split only; the chosen pair is then reported on test.

A turn counts as correct when the top intent is one of its labels. "Confident" turns are the
ones allowed to switch tasks, so a good threshold keeps confident turns very accurate while
leaving short, ambiguous answers unconfident.

Usage:
    python -m bench.router
"""

import argparse
import itertools
import json

import numpy as np

from bench.common import DATA_DIR, ResultWriter, ms, now, summarize
from bench.llm import load_cases
from tellerline.router.classifier import IntentClassifier
from tellerline.router.embedder import EMBEDDING_MODEL, Embedder
from tellerline.router.intents import EXAMPLES

MIN_SCORES = [0.60, 0.65, 0.70, 0.75, 0.80]
MIN_MARGINS = [0.0, 0.02, 0.04, 0.06]


def labelled_turns(split: str) -> list[dict]:
    turns = [
        {"id": case["id"], "text": case["user"], "intents": case["intents"]}
        for case in load_cases(split)
    ]
    for line in (DATA_DIR / f"dialogues_{split}.jsonl").read_text().splitlines():
        dialogue = json.loads(line)
        for index, turn in enumerate(dialogue["turns"]):
            turns.append(
                {
                    "id": f"{dialogue['id']}#{index}",
                    "text": turn["user"],
                    "intents": turn["intents"],
                }
            )
    return turns


def evaluate(classifier: IntentClassifier, turns: list[dict], vectors: np.ndarray) -> dict:
    correct = confident = confident_correct = 0
    mistakes = []
    for turn, vector in zip(turns, vectors, strict=True):
        prediction = classifier.score_vector(vector)
        ok = prediction.intent in turn["intents"]
        correct += ok
        confident += prediction.confident
        confident_correct += ok and prediction.confident
        if not ok:
            mistakes.append(
                {
                    "id": turn["id"],
                    "text": turn["text"],
                    "expected": turn["intents"],
                    "got": prediction.intent,
                    "score": round(prediction.score, 3),
                    "confident": prediction.confident,
                }
            )
    n = len(turns)
    return {
        "accuracy": correct / n,
        "confident_rate": confident / n,
        "confident_accuracy": confident_correct / confident if confident else None,
        "confident_mistakes": sum(1 for m in mistakes if m["confident"]),
        "mistakes": mistakes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--latency-runs", type=int, default=200)
    args = parser.parse_args()

    embedder = Embedder()
    classifier = IntentClassifier(embedder, EXAMPLES)
    turns = {split: labelled_turns(split) for split in ("dev", "test")}
    vectors = {split: embedder.embed([t["text"] for t in turns[split]]) for split in turns}

    # Sweep on dev. Prefer the fewest confident mistakes (a wrong switch derails a task), then
    # the most confident turns (fewer needless fallbacks to the general skill).
    sweep = []
    for min_score, min_margin in itertools.product(MIN_SCORES, MIN_MARGINS):
        classifier.min_score, classifier.min_margin = min_score, min_margin
        result = evaluate(classifier, turns["dev"], vectors["dev"])
        sweep.append({"min_score": min_score, "min_margin": min_margin, **result})
    best = min(sweep, key=lambda r: (r["confident_mistakes"], -r["confident_rate"]))
    classifier.min_score, classifier.min_margin = best["min_score"], best["min_margin"]

    results = {split: evaluate(classifier, turns[split], vectors[split]) for split in turns}

    texts = [t["text"] for t in turns["test"]]
    for text in texts[:10]:
        classifier.predict(text)  # warm up
    timings = []
    for i in range(args.latency_runs):
        start = now()
        classifier.predict(texts[i % len(texts)])
        timings.append(now() - start)
    latency = summarize(timings)

    config = {"model": EMBEDDING_MODEL, "examples": {k: len(v) for k, v in EXAMPLES.items()}}
    with ResultWriter("router", config) as writer:
        writer.summary(
            thresholds={"min_score": best["min_score"], "min_margin": best["min_margin"]},
            dev=results["dev"],
            test=results["test"],
            latency_s=latency,
            sweep=[{k: v for k, v in r.items() if k != "mistakes"} for r in sweep],
        )

    print(f"thresholds (chosen on dev): min_score {best['min_score']}, margin {best['min_margin']}")
    for split, result in results.items():
        print(
            f"{split}: top-intent accuracy {result['accuracy']:.0%}, confident on "
            f"{result['confident_rate']:.0%} of turns, confident accuracy "
            f"{(result['confident_accuracy'] or 0):.0%} "
            f"({result['confident_mistakes']} confident mistakes)"
        )
        for mistake in result["mistakes"]:
            flag = "CONFIDENT" if mistake["confident"] else "unsure"
            print(
                f"   {flag:<9} {mistake['text'][:60]!r}: expected {mistake['expected']}, "
                f"got {mistake['got']} ({mistake['score']})"
            )
    print(f"latency: p50 {ms(latency['p50'])} ms, p90 {ms(latency['p90'])} ms")
    print(f"Results: {writer.path}")


if __name__ == "__main__":
    main()
