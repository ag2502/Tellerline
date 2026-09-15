"""Benchmark Kokoro with British voices: time to first audio and speed, across runtimes.

Pipecat sends TTS one sentence at a time, so per-sentence time to first audio is what enters
the latency budget. Two runtimes are compared:

- ``onnx``: kokoro-onnx, as used by Pipecat's KokoroTTSService, over model precision (fp32,
  fp16, int8), execution provider (CPU or CoreML) and thread count. The M5 has 4 performance
  and 6 efficiency cores, and ONNX Runtime's default thread pool spans both.
- ``mlx``: the MLX Kokoro model on the GPU with the same espeak-ng phonemes
  (``tellerline.tts.kokoro_mlx``), in bf16 and 8-bit.

Usage:
    python -m bench.tts --repeats 3
    python -m bench.tts --engines mlx --repeats 10
"""

import argparse
import asyncio
import itertools
from collections import defaultdict
from collections.abc import Awaitable, Callable

import onnxruntime as ort
from kokoro_onnx import Kokoro

from bench.common import ResultWriter, ms, now, summarize
from tellerline.config import (
    KOKORO_CACHE_DIR,
    KOKORO_MLX_MODELS,
    KOKORO_MODEL_FILES,
    KOKORO_VOICES_PATH,
    TTS_LANG,
    TTS_UK_VOICES,
)
from tellerline.tts.kokoro_mlx import SAMPLE_RATE, KokoroMLX

PROVIDERS = {
    "cpu": ["CPUExecutionProvider"],
    "coreml": ["CoreMLExecutionProvider", "CPUExecutionProvider"],
}

# Typical first sentences of agent replies, from a short confirmation to a long one.
SENTENCES = {
    "short": "Your card is now frozen.",
    "medium": "Thanks, Aoife, the balance on your current account is one thousand, two hundred "
    "and fifty euro and forty cent.",
    "long": "I've opened a dispute for the payment of forty-nine euro and ninety-nine cent to "
    "StreamFlix on the second of September, and you'll get a letter about it within five "
    "working days.",
}

Synthesize = Callable[[str, str], Awaitable[dict[str, float]]]


def load_kokoro_onnx(variant: str = "fp32", provider: str = "cpu", threads: int = 0) -> Kokoro:
    """Load kokoro-onnx; ``threads=0`` keeps ONNX Runtime's default thread pool."""
    model_path = KOKORO_CACHE_DIR / KOKORO_MODEL_FILES[variant]
    if not model_path.exists() or not KOKORO_VOICES_PATH.exists():
        raise SystemExit("Kokoro model files are missing. Run: python scripts/download_models.py")
    options = ort.SessionOptions()
    if threads:
        options.intra_op_num_threads = threads
    session = ort.InferenceSession(
        str(model_path), sess_options=options, providers=PROVIDERS[provider]
    )
    return Kokoro.from_session(session, str(KOKORO_VOICES_PATH))


def onnx_synthesizer(kokoro: Kokoro) -> Synthesize:
    async def synthesize(text: str, voice: str) -> dict[str, float]:
        start = now()
        first_audio = None
        samples = 0
        async for audio, _ in kokoro.create_stream(text, voice=voice, lang=TTS_LANG):
            if first_audio is None:
                first_audio = now() - start
            samples += len(audio)
        return _timing(start, first_audio, samples)

    return synthesize


def mlx_synthesizer(kokoro: KokoroMLX) -> Synthesize:
    async def synthesize(text: str, voice: str) -> dict[str, float]:
        start = now()
        audio = kokoro.synthesize(text, voice)
        return _timing(start, now() - start, len(audio))

    return synthesize


def _timing(start: float, first_audio: float | None, samples: int) -> dict[str, float]:
    total = now() - start
    audio_s = samples / SAMPLE_RATE
    return {
        "first_audio_s": first_audio,
        "total_s": total,
        "audio_s": audio_s,
        "rtf": total / audio_s if audio_s else None,
    }


def configs(args: argparse.Namespace) -> list[tuple[dict, Callable[[], Synthesize]]]:
    """Each benchmark configuration and a loader that builds its synthesiser."""
    found = []
    if "onnx" in args.engines:
        for variant, provider, threads in itertools.product(
            args.onnx_variants, args.providers, args.threads
        ):
            found.append(
                (
                    {
                        "engine": "onnx",
                        "variant": variant,
                        "provider": provider,
                        "threads": threads,
                    },
                    lambda v=variant, p=provider, t=threads: onnx_synthesizer(
                        load_kokoro_onnx(v, p, t)
                    ),
                )
            )
    if "mlx" in args.engines:
        for variant in args.mlx_variants:
            found.append(
                (
                    {"engine": "mlx", "variant": variant, "provider": "gpu", "threads": 0},
                    lambda v=variant: mlx_synthesizer(KokoroMLX(KOKORO_MLX_MODELS[v], TTS_LANG)),
                )
            )
    return found


async def bench_config(
    label: dict, synthesize: Synthesize, voices: list[str], repeats: int, writer: ResultWriter
) -> dict:
    # Warm up: ONNX Runtime and CoreML compile on first use, MLX compiles kernels.
    for text in SENTENCES.values():
        await synthesize(text, voices[0])

    first_audio: dict[str, list[float]] = defaultdict(list)
    rtf: list[float] = []
    for repeat, voice, (length, text) in itertools.product(
        range(repeats), voices, SENTENCES.items()
    ):
        result = await synthesize(text, voice)
        first_audio[length].append(result["first_audio_s"])
        first_audio["all"].append(result["first_audio_s"])
        rtf.append(result["rtf"])
        writer.sample(**label, voice=voice, length=length, repeat=repeat, **result)
    return {
        **label,
        "first_audio_s": {length: summarize(values) for length, values in first_audio.items()},
        "rtf": summarize(rtf),
    }


def describe(label: dict) -> str:
    if label["engine"] == "mlx":
        return f"mlx/{label['variant']}"
    return f"onnx/{label['variant']}/{label['provider']}/threads={label['threads'] or 'default'}"


async def run(args: argparse.Namespace) -> None:
    results = []
    with ResultWriter("tts", {**vars(args), "lang": TTS_LANG, "sentences": SENTENCES}) as writer:
        for label, load in configs(args):
            try:
                synthesize = load()
                summary = await bench_config(label, synthesize, args.voices, args.repeats, writer)
            except Exception as error:  # a provider may reject a model variant
                print(f"{describe(label)}: failed ({type(error).__name__}: {error})")
                continue
            results.append(summary)
            stats = summary["first_audio_s"]
            print(
                f"{describe(label):<30} first audio p90: short {ms(stats['short']['p90'])} ms, "
                f"medium {ms(stats['medium']['p90'])} ms, long {ms(stats['long']['p90'])} ms; "
                f"RTF p50 {summary['rtf']['p50']:.3f}"
            )
        best = min(results, key=lambda s: s["first_audio_s"]["medium"]["p90"], default=None)
        writer.summary(configs=results, best=best)
    if best:
        print(f"Fastest for a medium sentence: {describe(best)}")
    print(f"Results: {writer.path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--voices", nargs="+", default=list(TTS_UK_VOICES))
    parser.add_argument("--engines", nargs="+", default=["onnx", "mlx"], choices=["onnx", "mlx"])
    parser.add_argument(
        "--onnx-variants",
        nargs="+",
        default=list(KOKORO_MODEL_FILES),
        choices=list(KOKORO_MODEL_FILES),
    )
    parser.add_argument("--providers", nargs="+", default=list(PROVIDERS), choices=list(PROVIDERS))
    parser.add_argument("--threads", nargs="+", type=int, default=[0, 4])
    parser.add_argument(
        "--mlx-variants",
        nargs="+",
        default=list(KOKORO_MLX_MODELS),
        choices=list(KOKORO_MLX_MODELS),
    )
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
