"""Parakeet TDT 0.6B v3 on MLX as a Pipecat speech-to-text service.

Pipecat buffers the caller's speech and hands over one segment when the VAD says they stopped
talking; the whole segment is transcribed at once, which Parakeet does in well under 100 ms.
"""

from collections.abc import AsyncGenerator, Callable
from typing import Protocol

import numpy as np
import soxr
from loguru import logger
from pipecat.frames.frames import ErrorFrame, Frame, StartFrame, TranscriptionFrame
from pipecat.services.settings import STTSettings
from pipecat.services.stt_service import SegmentedSTTService
from pipecat.transcriptions.language import Language
from pipecat.utils.time import time_now_iso8601
from pipecat.utils.tracing.service_decorators import traced_stt

from tellerline.config import STT_MODEL, STT_SAMPLE_RATE
from tellerline.services.mlx_thread import run_mlx


class Transcriber(Protocol):
    def generate(self, audio): ...


def load_parakeet(model_id: str = STT_MODEL) -> Transcriber:
    from mlx_audio.stt.utils import load_model

    return load_model(model_id)


class ParakeetMLXSTTService(SegmentedSTTService):
    def __init__(
        self,
        *,
        model: str = STT_MODEL,
        loader: Callable[[str], Transcriber] = load_parakeet,
        **kwargs,
    ):
        super().__init__(
            settings=STTSettings(model=model, language=Language.EN_GB),
            **kwargs,
        )
        self._model_id = model
        self._loader = loader
        self._model: Transcriber | None = None

    @property
    def wants_wav_segments(self) -> bool:
        return False  # raw 16-bit PCM, no WAV header

    def can_generate_metrics(self) -> bool:
        return True

    async def start(self, frame: StartFrame):
        await super().start(frame)
        if self._model is None:
            self._model = await run_mlx(self._loader, self._model_id)
            # Compile kernels now, not on the caller's first sentence.
            await run_mlx(self._transcribe, np.zeros(STT_SAMPLE_RATE, dtype=np.float32))

    def _transcribe(self, samples: np.ndarray) -> str:
        import mlx.core as mx

        return self._model.generate(mx.array(samples)).text.strip()

    @traced_stt
    async def _handle_transcription(
        self, transcript: str, is_final: bool, language: Language | None = None
    ):
        """Records the transcript as an OpenTelemetry span when tracing is enabled."""

    async def run_stt(self, audio: bytes) -> AsyncGenerator[Frame, None]:
        if self._model is None:
            yield ErrorFrame("Parakeet model not loaded")
            return

        await self.start_processing_metrics()
        samples = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0
        if self.sample_rate != STT_SAMPLE_RATE:
            samples = soxr.resample(samples, self.sample_rate, STT_SAMPLE_RATE).astype(np.float32)
        text = await run_mlx(self._transcribe, samples)
        await self.stop_processing_metrics()

        if text:
            logger.debug(f"Transcription: [{text}]")
            await self._handle_transcription(text, True, Language.EN_GB)
            yield TranscriptionFrame(text, self._user_id, time_now_iso8601(), Language.EN_GB)
