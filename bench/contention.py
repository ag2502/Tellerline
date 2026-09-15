"""Measure how Kokoro and Gemma slow each other down when both use the GPU at once.

In a live call, TTS starts on the first sentence while the LLM is still generating the rest
of the reply, so both run on the M5 GPU together. This benchmark times Kokoro's first audio
and the LLM's generation speed, first each on its own and then overlapping.

Usage:
    python -m bench.contention --model e4b --rounds 20
"""

import argparse
import threading
import time

from openai import OpenAI

from bench.common import RESULTS_DIR, ResultWriter, ms, now, summarize
from bench.llm import start_server
from bench.tts import SENTENCES
from tellerline.config import (
    KOKORO_MLX_MODELS,
    LLM_MODELS,
    LLM_SERVER_HOST,
    LLM_SERVER_PORT,
    TTS_DEFAULT_VOICE,
    TTS_LANG,
    TTS_MLX_VARIANT,
)
from tellerline.tts.kokoro_mlx import KokoroMLX

LLM_HEAD_START_S = 0.3
LONG_REPLY_PROMPT = [
    {
        "role": "user",
        "content": "In about 150 words, explain to a bank customer how a card dispute works.",
    }
]


def generation_speed(client: OpenAI, model_id: str) -> float:
    """Tokens per second of one long streamed completion, excluding time to first token."""
    start = now()
    first = None
    tokens = 0
    stream = client.chat.completions.create(
        model=model_id,
        messages=LONG_REPLY_PROMPT,
        stream=True,
        max_tokens=200,
        temperature=0.0,
        stream_options={"include_usage": True},
    )
    for chunk in stream:
        if chunk.choices and chunk.choices[0].delta.content and first is None:
            first = now()
        if chunk.usage:
            tokens = chunk.usage.completion_tokens
    elapsed = now() - (first or start)
    return tokens / elapsed if elapsed else 0.0


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--model", default="e4b", choices=list(LLM_MODELS))
    parser.add_argument("--rounds", type=int, default=20)
    parser.add_argument("--port", type=int, default=LLM_SERVER_PORT)
    args = parser.parse_args()

    model_id = LLM_MODELS[args.model]
    (RESULTS_DIR / "logs").mkdir(parents=True, exist_ok=True)
    server = start_server(model_id, args.port, RESULTS_DIR / "logs" / "mlx-server-contention.log")
    try:
        client = OpenAI(
            base_url=f"http://{LLM_SERVER_HOST}:{args.port}/v1", api_key="not-needed", timeout=120
        )
        kokoro = KokoroMLX(KOKORO_MLX_MODELS[TTS_MLX_VARIANT], TTS_LANG)
        text = SENTENCES["medium"]
        kokoro.synthesize(text, TTS_DEFAULT_VOICE)
        generation_speed(client, model_id)

        def tts_once() -> float:
            start = now()
            kokoro.synthesize(text, TTS_DEFAULT_VOICE)
            return now() - start

        tts_alone = [tts_once() for _ in range(args.rounds)]
        llm_alone = [generation_speed(client, model_id) for _ in range(max(3, args.rounds // 4))]

        tts_together: list[float] = []
        llm_together: list[float] = []
        for _ in range(args.rounds):
            speeds: list[float] = []
            worker = threading.Thread(
                target=lambda out=speeds: out.append(generation_speed(client, model_id))
            )
            worker.start()
            # Let the LLM get past prefill and into decoding before TTS starts, as in a call.
            time.sleep(LLM_HEAD_START_S)
            tts_together.append(tts_once())
            worker.join()
            llm_together.extend(speeds)

        summary = {
            "model": args.model,
            "tts_first_audio_s": {
                "alone": summarize(tts_alone),
                "with_llm": summarize(tts_together),
            },
            "llm_tokens_per_s": {
                "alone": summarize(llm_alone),
                "with_tts": summarize(llm_together),
            },
        }
        with ResultWriter("contention", vars(args)) as writer:
            writer.summary(**summary)

        tts, llm = summary["tts_first_audio_s"], summary["llm_tokens_per_s"]
        print(
            f"Kokoro medium sentence p90: alone {ms(tts['alone']['p90'])} ms, "
            f"while LLM decodes {ms(tts['with_llm']['p90'])} ms"
        )
        print(
            f"{args.model} generation p50: alone {llm['alone']['p50']:.1f} tok/s, "
            f"while TTS runs {llm['with_tts']['p50']:.1f} tok/s"
        )
        print(f"Results: {writer.path}")
    finally:
        server.terminate()
        server.wait(timeout=30)


if __name__ == "__main__":
    main()
