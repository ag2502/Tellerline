"""Parakeet TDT 0.6B v3 on MLX as a Pipecat speech-to-text service.

Pipecat buffers the caller's speech and hands over one segment when the VAD says they stopped
talking; the whole segment is transcribed at once, which Parakeet does in well under 100 ms. A
turn that came in several segments can be transcribed again in one pass (turn_transcript).
"""

import re
import time
from collections import deque
from collections.abc import AsyncGenerator, Callable
from functools import lru_cache
from typing import Protocol

import numpy as np
import soxr
from loguru import logger
from pipecat.frames.frames import (
    ErrorFrame,
    Frame,
    StartFrame,
    TranscriptionFrame,
)
from pipecat.services.settings import STTSettings
from pipecat.services.stt_service import SegmentedSTTService
from pipecat.transcriptions.language import Language
from pipecat.utils.time import time_now_iso8601
from pipecat.utils.tracing.service_decorators import traced_stt

from tellerline.config import STT_MODEL, STT_PRE_ROLL_S, STT_SAMPLE_RATE, STT_TTFS_P99_S
from tellerline.services.mlx_thread import Priority, run_mlx


class Transcriber(Protocol):
    def generate(self, audio): ...


class Timeline(Protocol):
    def note_transcription(self, milliseconds: float) -> None: ...


# Segments kept for transcribing a turn whole; a turn is rarely more than three.
SEGMENTS_KEPT = 8


@lru_cache(maxsize=2)
def load_parakeet(model_id: str = STT_MODEL) -> Transcriber:
    """Load Parakeet in bfloat16; the published float32 weights (2.3 GB) are twice what we need."""
    import mlx.core as mx
    from mlx_audio.stt.utils import load_model

    model = load_model(model_id)
    model.set_dtype(mx.bfloat16)
    # MLX is lazy: until the conversion is evaluated, the float32 weights stay in memory.
    mx.eval(model.parameters())
    return model


_DIGIT_GROUP_COMMA = re.compile(r"(?<=\d),(?=\d{3}\b)")


def clean_transcript(text: str) -> str:
    """Undo number formatting speech recognition adds: "45,127,890" becomes "45127890".

    Callers read out customer numbers and card digits, which must reach the model as digits.
    """
    return _DIGIT_GROUP_COMMA.sub("", text).strip()


def warm_up(model: Transcriber) -> None:
    """Run one inference so MLX compiles its kernels before a caller is waiting.

    The first inference on a fresh process takes around ten seconds; afterwards it's milliseconds.
    Call it on the MLX thread, once per process.
    """
    import mlx.core as mx

    model.generate(mx.array(np.zeros(STT_SAMPLE_RATE, dtype=np.float32)))


class ParakeetMLXSTTService(SegmentedSTTService):
    def __init__(
        self,
        *,
        model: str = STT_MODEL,
        loader: Callable[[str], Transcriber] = load_parakeet,
        timeline: "Timeline | None" = None,
        **kwargs,
    ):
        super().__init__(
            settings=STTSettings(model=model, language=Language.EN_GB),
            ttfs_p99_latency=STT_TTFS_P99_S,
            **kwargs,
        )
        self._model_id = model
        self._loader = loader
        self._timeline = timeline
        self._model: Transcriber | None = None
        # The caller's latest segments as said, at 16 kHz, with their transcripts, for
        # transcribing a turn of several segments in one pass (turn_transcript).
        self._segments: deque[tuple[np.ndarray, str]] = deque(maxlen=SEGMENTS_KEPT)

    @property
    def wants_wav_segments(self) -> bool:
        return False  # raw 16-bit PCM, no WAV header

    def can_generate_metrics(self) -> bool:
        return True

    async def start(self, frame: StartFrame):
        await super().start(frame)
        if self._model is None:
            # Cached per process; the agent launcher loads and warms it before the first call.
            self._model = await run_mlx(self._loader, self._model_id)

    async def setup(self, setup):
        await super().setup(setup)
        # Pipecat keeps one second of audio before speech is confirmed; keep STT_PRE_ROLL_S.
        self._audio_buffer_size_1s = int(self.sample_rate * 2 * STT_PRE_ROLL_S)

    async def turn_transcript(self, text: str) -> str | None:
        """The caller's turn transcribed in one pass, when it arrived in more than one segment.

        Every pause the VAD hears ends a segment, and each is transcribed on its own as it ends.
        A word the caller started just before the VAD declared the pause can land half in each
        segment, and Parakeet then drops it or writes it twice: on phone audio "four five one
        two seven. | seven eight nine zero", nine digits for an eight-digit number. Transcribed
        whole, with the context on both sides, the same audio comes out right. The segments are
        contiguous (the buffer starts afresh where the last one ended), so joined they are the
        caller's speech as it was said.

        `text` is the turn as the agent has it: everything the caller said since it was last
        heard, which is the latest segments' transcripts joined. Those segments are the turn's;
        none if the latest transcripts don't make up `text`.
        """
        segments = self._turn_segments(text)
        if len(segments) < 2 or self._model is None:
            return None
        started = time.perf_counter()
        padding = np.zeros(int(STT_SAMPLE_RATE * self._trailing_silence_secs), dtype=np.float32)
        audio = np.concatenate([*segments, padding])
        text = await run_mlx(self._transcribe, audio, priority=Priority.TRANSCRIBE)
        if self._timeline is not None:
            self._timeline.note_transcription((time.perf_counter() - started) * 1000)
        return text or None

    def _turn_segments(self, text: str) -> list[np.ndarray]:
        """The latest segments whose transcripts, joined, are `text`, oldest first."""
        turn = text.split()
        picked: list[np.ndarray] = []
        words: list[str] = []
        for samples, said in reversed(self._segments):
            if not picked and not said.split():
                continue  # a noise after the turn, transcribed as nothing
            words = said.split() + words
            picked.append(samples)
            if words == turn:
                return picked[::-1]
            if len(words) > len(turn) or turn[len(turn) - len(words) :] != words:
                return []
        return []

    def _transcribe(self, samples: np.ndarray) -> str:
        import mlx.core as mx

        return clean_transcript(self._model.generate(mx.array(samples)).text)

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
        started = time.perf_counter()
        samples = np.frombuffer(audio, dtype=np.int16).astype(np.float32) / 32768.0
        if self.sample_rate != STT_SAMPLE_RATE:
            samples = soxr.resample(samples, self.sample_rate, STT_SAMPLE_RATE).astype(np.float32)
        text = await run_mlx(self._transcribe, samples, priority=Priority.TRANSCRIBE)
        # The segment as said, without the silence padded on for transcription.
        padded = int(STT_SAMPLE_RATE * self._trailing_silence_secs)
        self._segments.append((samples[: max(0, len(samples) - padded)], text))
        await self.stop_processing_metrics()
        if self._timeline is not None:
            self._timeline.note_transcription((time.perf_counter() - started) * 1000)

        if text:
            logger.debug(f"Transcription: [{text}]")
            await self._handle_transcription(text, True, Language.EN_GB)
            # Each segment is transcribed whole, so its transcript is final: turn detection can
            # release the turn as soon as it arrives instead of waiting out a timer.
            yield TranscriptionFrame(
                text, self._user_id, time_now_iso8601(), Language.EN_GB, finalized=True
            )
