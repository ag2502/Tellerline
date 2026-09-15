"""Render the same agent lines in each British Kokoro voice, to choose the agent's voice by ear.

Usage:
    python scripts/voice_samples.py            # writes results/samples/<voice>.wav
"""

import argparse
from pathlib import Path

import numpy as np
import soundfile as sf

from tellerline.config import KOKORO_MLX_MODELS, TTS_LANG, TTS_MLX_VARIANT
from tellerline.tts.kokoro_mlx import SAMPLE_RATE, KokoroMLX

LINES = [
    "Hello, you're through to Tellerline Bank. I'm an AI assistant, and this call may be recorded.",
    "Before I can help, could I have your eight-digit customer number and your date of birth?",
    "Thanks, Aoife. The balance on your current account is one thousand, two hundred and fifty "
    "euro and forty cent.",
    "I've frozen the card ending four two one seven, so nobody can use it.",
]
PAUSE_S = 0.6
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--voices",
        nargs="+",
        default=[
            "bf_alice",
            "bf_emma",
            "bf_isabella",
            "bf_lily",
            "bm_daniel",
            "bm_fable",
            "bm_george",
            "bm_lewis",
        ],
    )
    args = parser.parse_args()

    kokoro = KokoroMLX(KOKORO_MLX_MODELS[TTS_MLX_VARIANT], TTS_LANG)
    out_dir = RESULTS_DIR / "samples"
    out_dir.mkdir(parents=True, exist_ok=True)
    silence = np.zeros(int(PAUSE_S * SAMPLE_RATE), dtype=np.float32)
    for voice in args.voices:
        parts = []
        for line in LINES:
            parts += [kokoro.synthesize(line, voice), silence]
        path = out_dir / f"{voice}.wav"
        sf.write(path, np.concatenate(parts), SAMPLE_RATE)
        print(path)


if __name__ == "__main__":
    main()
