"""Benchmark Parakeet TDT 0.6B v3 on MLX: transcription latency for caller-length utterances.

Test audio is generated with Kokoro's British voices, so no dataset download is needed.
Latency is what this measures. Word error rate on synthetic speech is only a sanity check
that transcription works; real accuracy is measured on recorded speech in a later phase.
Each utterance is also run through a phone-band version (8 kHz), which is what callers on
the Asterisk line will sound like.

Usage:
    python -m bench.stt --repeats 5
"""

import argparse
import re
from collections import defaultdict

import jiwer
import mlx.core as mx
import numpy as np
import soxr
from mlx_audio.stt.utils import load_model

from bench.common import ResultWriter, ms, now, summarize
from tellerline.config import (
    KOKORO_MLX_MODELS,
    STT_MODEL,
    STT_SAMPLE_RATE,
    TTS_LANG,
    TTS_MLX_VARIANT,
    TTS_UK_VOICES,
)
from tellerline.tts.kokoro_mlx import SAMPLE_RATE as TTS_SAMPLE_RATE
from tellerline.tts.kokoro_mlx import KokoroMLX

# Things callers say, without digits, so reference and transcript normalise the same way.
UTTERANCES = [
    "Hello.",
    "I've lost my debit card.",
    "What's the balance on my current account?",
    "Can you read me the last few transactions on my savings account, please?",
    "There's a payment I don't recognise and I'd like to block my card straight away.",
    "I was charged twice by the hotel yesterday, and I want to dispute one of the payments "
    "because I only stayed one night.",
]


def normalise(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s']", " ", text.casefold())).strip()


def phone_band(audio: np.ndarray) -> np.ndarray:
    """Simulate a narrowband phone call: down to 8 kHz and back up to 16 kHz."""
    narrow = soxr.resample(audio, STT_SAMPLE_RATE, 8_000)
    return soxr.resample(narrow, 8_000, STT_SAMPLE_RATE).astype(np.float32)


def make_clips(voices: list[str]) -> list[dict]:
    kokoro = KokoroMLX(KOKORO_MLX_MODELS[TTS_MLX_VARIANT], TTS_LANG)
    clips = []
    for voice in voices:
        for text in UTTERANCES:
            audio = kokoro.synthesize(text, voice)
            audio16 = soxr.resample(audio, TTS_SAMPLE_RATE, STT_SAMPLE_RATE).astype(np.float32)
            clips.append({"voice": voice, "text": text, "band": "wide", "audio": audio16})
            clips.append(
                {"voice": voice, "text": text, "band": "phone", "audio": phone_band(audio16)}
            )
    return clips


def transcribe(model, audio: np.ndarray) -> tuple[str, float]:
    start = now()
    result = model.generate(mx.array(audio))
    return result.text, now() - start


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--voices", nargs="+", default=list(TTS_UK_VOICES))
    args = parser.parse_args()

    clips = make_clips(args.voices)
    load_start = now()
    model = load_model(STT_MODEL)
    load_s = now() - load_start
    for clip in clips[:3]:
        transcribe(model, clip["audio"])  # compile kernels before timing

    latency: dict[str, list[float]] = defaultdict(list)
    errors: dict[str, list[float]] = defaultdict(list)
    config = {"model": STT_MODEL, "repeats": args.repeats, "voices": args.voices}
    with ResultWriter("stt", config) as writer:
        for repeat in range(args.repeats):
            for clip in clips:
                text, seconds = transcribe(model, clip["audio"])
                audio_s = len(clip["audio"]) / STT_SAMPLE_RATE
                wer = jiwer.wer(normalise(clip["text"]), normalise(text) or "<empty>")
                bucket = "under_3s" if audio_s < 3 else "3_to_6s" if audio_s < 6 else "over_6s"
                latency[bucket].append(seconds)
                latency[f"all_{clip['band']}"].append(seconds)
                if repeat == 0:
                    errors[clip["band"]].append(wer)
                writer.sample(
                    voice=clip["voice"],
                    band=clip["band"],
                    reference=clip["text"],
                    transcript=text,
                    audio_s=audio_s,
                    latency_s=seconds,
                    wer=wer,
                    repeat=repeat,
                )
        summary = {
            "load_s": load_s,
            "latency_s": {name: summarize(values) for name, values in latency.items()},
            "wer_synthetic": {band: sum(v) / len(v) for band, v in errors.items()},
        }
        writer.summary(**summary)

    print(f"model load {load_s:.1f} s")
    for name, stats in summary["latency_s"].items():
        print(f"{name:>10}: p50 {ms(stats['p50'])} ms, p90 {ms(stats['p90'])} ms (n={stats['n']})")
    for band, wer in summary["wer_synthetic"].items():
        print(f"synthetic-speech WER ({band}): {wer:.1%}")
    print(f"Results: {writer.path}")


if __name__ == "__main__":
    main()
