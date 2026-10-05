"""Bring the models back into memory while the greeting plays.

On a Mac in everyday use, macOS compresses or swaps out the memory of models that have sat idle:
the first reply after an idle spell took 11 s (Parakeet 3.9 s, Gemma's first token 7.0 s; D-027),
against about a second once the models are back. The greeting is pre-rendered, so the GPU has
nothing to do while it plays. One small pass through each model in that time brings it back
before the caller has finished their first sentence.

Everything here runs at the MLX thread's lowest priority, behind any real turn, and only when no
other call is in progress: with a call running, the models are already in use and in memory.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable

from loguru import logger

from tellerline.services.mlx_thread import Priority, run_mlx

_active_calls = 0
_tasks: set[asyncio.Task] = set()


def call_started(rewarm: Callable[[], Awaitable[None]]) -> None:
    """Note a call starting; re-warm the models in the background if it's the only one."""
    global _active_calls
    _active_calls += 1
    if _active_calls == 1:
        task = asyncio.ensure_future(_timed(rewarm))
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)


def call_ended() -> None:
    global _active_calls
    _active_calls = max(0, _active_calls - 1)


async def _timed(rewarm: Callable[[], Awaitable[None]]) -> None:
    started = time.perf_counter()
    try:
        await rewarm()
    except Exception as error:  # a failed warm-up must never take a call down
        logger.warning(f"Re-warming the models failed: {type(error).__name__}: {error}")
        return
    logger.info(f"Models re-warmed in {(time.perf_counter() - started) * 1000:.0f} ms")


async def rewarm_models(llm_model: str, voice: str) -> None:
    """One small pass through Parakeet, Kokoro, the intent classifier and Gemma."""
    from datetime import date

    from openai import AsyncOpenAI

    from tellerline.brain import opening_history
    from tellerline.config import KOKORO_MLX_MODELS, STT_MODEL, TTS_MLX_VARIANT
    from tellerline.llm_server import base_url
    from tellerline.router.classifier import default_classifier
    from tellerline.router.skills import build_skill_prompt
    from tellerline.services.stt import load_parakeet
    from tellerline.services.stt import warm_up as warm_up_stt
    from tellerline.services.tts import load_kokoro
    from tellerline.services.tts import warm_up as warm_up_tts

    low = Priority.LATER_AUDIO
    parakeet = await run_mlx(load_parakeet, STT_MODEL, priority=low)
    await run_mlx(warm_up_stt, parakeet, priority=low)
    kokoro = await run_mlx(load_kokoro, KOKORO_MLX_MODELS[TTS_MLX_VARIANT], priority=low)
    await run_mlx(warm_up_tts, kokoro, voice, priority=low)
    await asyncio.to_thread(default_classifier().predict, "hello")
    # A caller's first turn goes to the identity skill; one token on its prompt pages Gemma in
    # and keeps the prompt's prefix cached.
    messages = [
        {"role": "system", "content": build_skill_prompt("identity", date.today(), False)},
        *opening_history(),
        {"role": "user", "content": "Hello."},
    ]
    client = AsyncOpenAI(base_url=base_url(), api_key="not-needed")
    try:
        await client.chat.completions.create(model=llm_model, messages=messages, max_tokens=1)
    finally:
        await client.close()
