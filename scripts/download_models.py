"""Download the Phase 0 models so benchmarks and the agent start without network access.

MLX models go to the Hugging Face cache; the kokoro-onnx baseline files go where Pipecat's
KokoroTTSService looks for them.

Usage:
    python scripts/download_models.py                 # everything (about 12.6 GB)
    python scripts/download_models.py --only e4b stt  # a subset
"""

import argparse
import sys
import urllib.request
from pathlib import Path

from huggingface_hub import snapshot_download

from tellerline.config import (
    KOKORO_CACHE_DIR,
    KOKORO_MLX_MODELS,
    KOKORO_MODEL_FILES,
    KOKORO_RELEASE_URL,
    KOKORO_VOICES_PATH,
    LLM_MODELS,
    STT_MODEL,
)
from tellerline.tts.kokoro_mlx import MODEL_FILES

TARGETS = [*LLM_MODELS, "stt", "tts"]


def download_file(url: str, destination: Path) -> None:
    if destination.exists():
        print(f"  already present: {destination}")
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    partial = destination.with_suffix(destination.suffix + ".part")

    last_percent = -1

    def progress(blocks: int, block_size: int, total: int) -> None:
        nonlocal last_percent
        if total <= 0:
            return
        percent = min(blocks * block_size, total) * 100 // total
        if percent != last_percent and percent % 10 == 0:
            last_percent = percent
            sys.stdout.write(f"\r  {destination.name}: {percent}% of {total / 1e6:.0f} MB")
            sys.stdout.flush()

    urllib.request.urlretrieve(url, partial, reporthook=progress)
    partial.rename(destination)
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--only", nargs="+", choices=TARGETS, default=TARGETS)
    args = parser.parse_args()

    for target in args.only:
        if target in LLM_MODELS:
            print(f"LLM {target}: {LLM_MODELS[target]}")
            snapshot_download(LLM_MODELS[target])
        elif target == "stt":
            print(f"STT: {STT_MODEL}")
            snapshot_download(STT_MODEL)
        elif target == "tts":
            for repo_id in KOKORO_MLX_MODELS.values():
                print(f"TTS: {repo_id}")
                snapshot_download(repo_id, allow_patterns=MODEL_FILES)
            print("TTS baseline: Kokoro v1.0 (kokoro-onnx), fp32, fp16 and int8")
            for filename in KOKORO_MODEL_FILES.values():
                download_file(f"{KOKORO_RELEASE_URL}/{filename}", KOKORO_CACHE_DIR / filename)
            download_file(f"{KOKORO_RELEASE_URL}/{KOKORO_VOICES_PATH.name}", KOKORO_VOICES_PATH)
    print("Done.")


if __name__ == "__main__":
    main()
