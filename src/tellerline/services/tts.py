"""Kokoro-82M on MLX as a Pipecat text-to-speech service (see ``tellerline.tts.kokoro_mlx``).

Pipecat hands over one sentence at a time. Each sentence is synthesised in one pass (about a
twentieth of real time on the M5) and sent out in short chunks, so an interruption stops
playback quickly.
"""

from collections.abc import AsyncGenerator, Callable
from functools import lru_cache
from typing import Protocol

import numpy as np
from pipecat.frames.frames import ErrorFrame, Frame, StartFrame, TTSAudioRawFrame
from pipecat.services.settings import TTSSettings
from pipecat.services.tts_service import TTSService
from pipecat.transcriptions.language import Language

from tellerline.config import KOKORO_MLX_MODELS, TTS_DEFAULT_VOICE, TTS_LANG, TTS_MLX_VARIANT
from tellerline.services.mlx_thread import run_mlx
from tellerline.tts.kokoro_mlx import SAMPLE_RATE as KOKORO_SAMPLE_RATE

CHUNK_SECONDS = 0.1


class Synthesizer(Protocol):
    def synthesize(self, text: str, voice: str, speed: float = 1.0) -> np.ndarray: ...


@lru_cache(maxsize=2)
def load_kokoro(repo_id: str) -> Synthesizer:
    from tellerline.tts.kokoro_mlx import KokoroMLX

    return KokoroMLX(repo_id, TTS_LANG)


def warm_up(engine: Synthesizer, voice: str = TTS_DEFAULT_VOICE) -> None:
    """Synthesise once so MLX compiles Kokoro's kernels. Run on the MLX thread, once per process."""
    engine.synthesize("Hello there.", voice)


class KokoroMLXTTSService(TTSService):
    def __init__(
        self,
        *,
        voice: str = TTS_DEFAULT_VOICE,
        model: str = KOKORO_MLX_MODELS[TTS_MLX_VARIANT],
        speed: float = 1.0,
        loader: Callable[[str], Synthesizer] = load_kokoro,
        **kwargs,
    ):
        super().__init__(
            push_start_frame=True,
            push_stop_frames=True,
            sample_rate=KOKORO_SAMPLE_RATE,
            settings=TTSSettings(model=model, voice=voice, language=TTS_LANG),
            **kwargs,
        )
        self._model_id = model
        self._speed = speed
        self._loader = loader
        self._engine: Synthesizer | None = None

    def can_generate_metrics(self) -> bool:
        return True

    def language_to_service_language(self, language: Language) -> str | None:
        return TTS_LANG if str(language).lower().startswith("en") else None

    async def start(self, frame: StartFrame):
        await super().start(frame)
        if self._engine is None:
            # Cached per process; the agent launcher loads and warms it before the first call.
            self._engine = await run_mlx(self._loader, self._model_id)

    async def run_tts(self, text: str, context_id: str) -> AsyncGenerator[Frame, None]:
        if self._engine is None:
            yield ErrorFrame("Kokoro model not loaded")
            return
        await self.start_tts_usage_metrics(text)
        try:
            audio = await run_mlx(self._engine.synthesize, text, self._settings.voice, self._speed)
        finally:
            await self.stop_ttfb_metrics()
        pcm = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16).tobytes()
        step = int(self.sample_rate * CHUNK_SECONDS) * 2  # 16-bit samples
        for start in range(0, len(pcm), step):
            yield TTSAudioRawFrame(
                audio=pcm[start : start + step],
                sample_rate=self.sample_rate,
                num_channels=1,
                context_id=context_id,
            )
