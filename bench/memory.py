"""Measure the memory each model needs, one component per fresh process.

All components run on MLX and report unified (GPU) memory through ``mlx.core``.

Usage:
    python -m bench.memory                      # all components
    python -m bench.memory --component stt      # one component, in this process
"""

import argparse
import json
import resource
import subprocess
import sys
from datetime import date

import numpy as np

from bench.common import ResultWriter
from tellerline.config import LLM_CHAT_TEMPLATE_ARGS, LLM_MODELS, STT_MODEL, STT_SAMPLE_RATE

GB = 1024**3
COMPONENTS = [f"llm-{key}" for key in LLM_MODELS] + ["stt", "tts"]


def peak_rss_gb() -> float:
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / GB  # bytes on macOS


def measure_llm(key: str) -> dict:
    import mlx.core as mx
    from mlx_lm import generate, load

    from tellerline.prompts import build_system_prompt

    model, tokenizer = load(LLM_MODELS[key])
    loaded = mx.get_active_memory() / GB
    messages = [
        {"role": "system", "content": build_system_prompt(date(2026, 9, 14))},
        {"role": "user", "content": "What's the balance on my current account?"},
    ]
    prompt = tokenizer.apply_chat_template(
        messages, add_generation_prompt=True, **LLM_CHAT_TEMPLATE_ARGS
    )
    generate(model, tokenizer, prompt, max_tokens=60)
    return {
        "weights_gb": loaded,
        "peak_gb": mx.get_peak_memory() / GB,
        "rss_peak_gb": peak_rss_gb(),
    }


def measure_stt() -> dict:
    import mlx.core as mx
    from mlx_audio.stt.utils import load_model

    model = load_model(STT_MODEL)
    loaded = mx.get_active_memory() / GB
    rng = np.random.default_rng(0)
    audio = (rng.standard_normal(STT_SAMPLE_RATE * 8) * 0.05).astype(np.float32)
    model.generate(mx.array(audio))
    return {
        "weights_gb": loaded,
        "peak_gb": mx.get_peak_memory() / GB,
        "rss_peak_gb": peak_rss_gb(),
    }


def measure_tts() -> dict:
    import mlx.core as mx

    from bench.tts import SENTENCES
    from tellerline.config import KOKORO_MLX_MODELS, TTS_DEFAULT_VOICE, TTS_LANG, TTS_MLX_VARIANT
    from tellerline.tts.kokoro_mlx import KokoroMLX

    kokoro = KokoroMLX(KOKORO_MLX_MODELS[TTS_MLX_VARIANT], TTS_LANG)
    loaded = mx.get_active_memory() / GB
    kokoro.synthesize(SENTENCES["long"], TTS_DEFAULT_VOICE)
    return {
        "weights_gb": loaded,
        "peak_gb": mx.get_peak_memory() / GB,
        "rss_peak_gb": peak_rss_gb(),
    }


def measure(component: str) -> dict:
    if component.startswith("llm-"):
        return measure_llm(component.removeprefix("llm-"))
    return {"stt": measure_stt, "tts": measure_tts}[component]()


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--component", choices=COMPONENTS)
    args = parser.parse_args()

    if args.component:
        print(json.dumps(measure(args.component)))
        return

    results = {}
    with ResultWriter("memory", {"components": COMPONENTS}) as writer:
        for component in COMPONENTS:
            output = subprocess.run(
                [sys.executable, "-m", "bench.memory", "--component", component],
                capture_output=True,
                text=True,
                check=True,
            ).stdout
            results[component] = json.loads(output.strip().splitlines()[-1])
            writer.sample(component=component, **results[component])
            print(component, {k: round(v, 2) for k, v in results[component].items()})
        writer.summary(components=results)
    print(f"Results: {writer.path}")


if __name__ == "__main__":
    main()
