"""How long a reply's text waits for its first audio: whole sentences vs clauses and the cache.

Before, Kokoro rendered each sentence whole before any of it played, so a long spoken result
(five transactions read as one sentence) kept the caller waiting for over a second. Now the
first clause renders alone, and fixed openings come straight from the cache filled at start-up
(``tellerline.tts.chunks``, ``tellerline.services.tts``).

Replies are every spoken result template, rendered from the mock bank answers the dialogue
benchmark uses, plus the agent's fixed phrases.

Usage:
    python -m bench.first_audio --repeats 5
"""

import argparse
import time

from bench.common import ResultWriter, ms, summarize
from bench.llm import BENCH_TODAY, MOCK_TOOL_RESULTS
from tellerline.agent.__main__ import fixed_phrases
from tellerline.banking.responses import respond
from tellerline.config import KOKORO_MLX_MODELS, TTS_DEFAULT_VOICE, TTS_MLX_VARIANT
from tellerline.services.mlx_thread import limit_mlx_cache
from tellerline.services.tts import PhraseCache, load_kokoro, warm_phrases
from tellerline.tts.chunks import sentences, speech_chunks

ARGUMENTS = {
    "verify_identity": {"customer_number": "45127890", "date_of_birth": "1991-03-03"},
    "get_balance": {"account": "current"},
    "get_recent_transactions": {"account": "current", "count": 3},
    "freeze_card": {"card_last_four": "4217", "reason": "stolen"},
    "order_replacement_card": {"card_last_four": "4217"},
    "dispute_transaction": {"merchant": "Pizza Palace", "amount": 22.5, "date": "2026-09-12"},
    "transfer_to_human": {},
    "end_call": {},
}
FIVE_TRANSACTIONS = {
    "transactions": [
        {"date": "2026-09-14", "merchant": "Bewley's Café", "amount_eur": -8.31},
        {"date": "2026-09-13", "merchant": "Aldi", "amount_eur": -52.10},
        {"date": "2026-09-12", "merchant": "Dublin Bus", "amount_eur": -2.00},
        {"date": "2026-09-11", "merchant": "Netflix", "amount_eur": -13.99},
        {"date": "2026-09-11", "merchant": "Salary, Acme Ltd", "amount_eur": 2650.00},
    ]
}


def replies() -> dict[str, str]:
    spoken = {
        tool: respond(tool, ARGUMENTS[tool], result, BENCH_TODAY)
        for tool, result in MOCK_TOOL_RESULTS.items()
    }
    spoken["get_recent_transactions (five)"] = respond(
        "get_recent_transactions", {"account": "current"}, FIVE_TRANSACTIONS, BENCH_TODAY
    )
    return spoken


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--voice", default=TTS_DEFAULT_VOICE)
    args = parser.parse_args()

    limit_mlx_cache()
    engine = load_kokoro(KOKORO_MLX_MODELS[TTS_MLX_VARIANT])
    engine.synthesize("Hello there.", args.voice)
    cache = PhraseCache()
    warm_phrases(engine, fixed_phrases(), args.voice, cache=cache)

    def render_ms(text: str) -> float:
        start = time.perf_counter()
        engine.synthesize(text, args.voice)
        return (time.perf_counter() - start) * 1000

    results: dict[str, list[float]] = {"sentence": [], "clause": [], "clause_cached": []}
    config = {"repeats": args.repeats, "voice": args.voice}
    with ResultWriter("first_audio", config) as writer:
        for name, text in replies().items():
            first_sentence = sentences(text)[0]
            first_chunk = speech_chunks(text)[0].text
            cached = cache.get(args.voice, 1.0, first_chunk) is not None
            for repeat in range(args.repeats):
                sentence_ms = render_ms(first_sentence)
                clause_ms = render_ms(first_chunk)
                served_ms = 0.0 if cached else clause_ms
                results["sentence"].append(sentence_ms)
                results["clause"].append(clause_ms)
                results["clause_cached"].append(served_ms)
                writer.sample(
                    reply=name,
                    repeat=repeat,
                    first_sentence=first_sentence,
                    first_chunk=first_chunk,
                    cached=cached,
                    sentence_ms=sentence_ms,
                    clause_ms=clause_ms,
                    served_ms=served_ms,
                )
            print(
                f"{name:<32} sentence {sentence_ms:5.0f} ms  clause {clause_ms:5.0f} ms  "
                f"{'cached' if cached else 'rendered'}  | {first_chunk}"
            )
        stats = {key: summarize(values) for key, values in results.items()}
        writer.summary(first_audio_ms=stats, cached_phrases=len(cache))

    for key, label in [
        ("sentence", "whole first sentence"),
        ("clause", "first clause, rendered"),
        ("clause_cached", "first clause, cache"),
    ]:
        s = stats[key]
        print(f"{label:<24} p50 {ms(s['p50'] / 1000)} ms  p90 {ms(s['p90'] / 1000)} ms")
    print(f"Results: {writer.path}")


if __name__ == "__main__":
    main()
