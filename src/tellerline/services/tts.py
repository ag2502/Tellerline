"""Kokoro-82M on MLX as a Pipecat text-to-speech service (see ``tellerline.tts.kokoro_mlx``).

Pipecat hands over one sentence at a time, and each sentence is spoken clause by clause
(``tellerline.tts.chunks``): the first clause is rendered and sent while the rest render, so the
caller waits for one short render rather than the whole sentence. Audio goes out in short
frames, so an interruption stops playback quickly.

Rendered clauses are kept in a cache shared by every call. Fixed phrases (the greeting,
follow-up questions, the opening of each spoken result) are rendered once at start-up, so most
replies begin without waiting for Kokoro at all.
"""

import threading
from collections import OrderedDict
from collections.abc import AsyncGenerator, Callable, Iterable, Iterator
from functools import lru_cache
from typing import Protocol

import numpy as np
from pipecat.frames.frames import ErrorFrame, Frame, StartFrame, TTSAudioRawFrame
from pipecat.services.settings import TTSSettings
from pipecat.services.tts_service import TTSService
from pipecat.transcriptions.language import Language
from pipecat.utils.tracing.service_decorators import traced_tts

from tellerline.config import KOKORO_MLX_MODELS, TTS_DEFAULT_VOICE, TTS_LANG, TTS_MLX_VARIANT
from tellerline.services.mlx_thread import run_mlx
from tellerline.tts.chunks import SENTENCE_PAUSE_S, speech_chunks
from tellerline.tts.kokoro_mlx import SAMPLE_RATE as KOKORO_SAMPLE_RATE

CHUNK_SECONDS = 0.1
# A clause is one to three seconds of 24 kHz, 16-bit audio (50 to 150 KB), so 400 entries stay
# within about 50 MB.
CACHE_ENTRIES = 400


class Synthesizer(Protocol):
    def synthesize(self, text: str, voice: str, speed: float = 1.0) -> np.ndarray: ...


@lru_cache(maxsize=2)
def load_kokoro(repo_id: str) -> Synthesizer:
    from tellerline.tts.kokoro_mlx import KokoroMLX

    return KokoroMLX(repo_id, TTS_LANG)


def warm_up(engine: Synthesizer, voice: str = TTS_DEFAULT_VOICE) -> None:
    """Synthesise once so MLX compiles Kokoro's kernels. Run on the MLX thread, once per process."""
    engine.synthesize("Hello there.", voice)


def to_pcm(audio: np.ndarray) -> bytes:
    """Float audio in [-1, 1] as 16-bit little-endian PCM."""
    return (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16).tobytes()


class PhraseCache:
    """Rendered clauses as PCM, by voice, speed and text; the least recently used goes first."""

    def __init__(self, max_entries: int = CACHE_ENTRIES):
        self.max_entries = max_entries
        self.hits = 0
        self.misses = 0
        self._entries: OrderedDict[tuple[str, float, str], bytes] = OrderedDict()
        self._lock = threading.Lock()  # warm-up fills it from the MLX thread

    def __len__(self) -> int:
        return len(self._entries)

    def get(self, voice: str, speed: float, text: str) -> bytes | None:
        with self._lock:
            pcm = self._entries.get((voice, speed, text))
            if pcm is None:
                self.misses += 1
                return None
            self._entries.move_to_end((voice, speed, text))
            self.hits += 1
            return pcm

    def put(self, voice: str, speed: float, text: str, pcm: bytes) -> None:
        with self._lock:
            self._entries[(voice, speed, text)] = pcm
            self._entries.move_to_end((voice, speed, text))
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)


PHRASES = PhraseCache()


def warm_phrases(
    engine: Synthesizer,
    phrases: Iterable[str],
    voice: str = TTS_DEFAULT_VOICE,
    speed: float = 1.0,
    cache: PhraseCache = PHRASES,
) -> int:
    """Render every clause of ``phrases`` into the cache; returns how many were rendered.

    Run on the MLX thread at start-up, before any call.
    """
    rendered = 0
    for phrase in phrases:
        for chunk in speech_chunks(phrase):
            if cache.get(voice, speed, chunk.text) is None:
                audio = engine.synthesize(chunk.text, voice, speed)
                cache.put(voice, speed, chunk.text, to_pcm(audio))
                rendered += 1
    return rendered


class KokoroMLXTTSService(TTSService):
    def __init__(
        self,
        *,
        voice: str = TTS_DEFAULT_VOICE,
        model: str = KOKORO_MLX_MODELS[TTS_MLX_VARIANT],
        speed: float = 1.0,
        loader: Callable[[str], Synthesizer] = load_kokoro,
        cache: PhraseCache = PHRASES,
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
        self._cache = cache
        self._engine: Synthesizer | None = None
        self._last_context_id: str | None = None

    def can_generate_metrics(self) -> bool:
        return True

    def language_to_service_language(self, language: Language) -> str | None:
        return TTS_LANG if str(language).lower().startswith("en") else None

    async def start(self, frame: StartFrame):
        await super().start(frame)
        if self._engine is None:
            # Cached per process; the agent launcher loads and warms it before the first call.
            self._engine = await run_mlx(self._loader, self._model_id)

    @traced_tts
    async def run_tts(self, text: str, context_id: str) -> AsyncGenerator[Frame, None]:
        if self._engine is None:
            yield ErrorFrame("Kokoro model not loaded")
            return
        await self.start_tts_usage_metrics(text)
        voice = self._settings.voice
        if context_id == self._last_context_id:
            # A later sentence of the same reply gets the pause a listener expects.
            for frame in self._silence(SENTENCE_PAUSE_S, context_id):
                yield frame
        self._last_context_id = context_id

        waiting = True
        try:
            for chunk in speech_chunks(text):
                pcm = self._cache.get(voice, self._speed, chunk.text)
                if pcm is None:
                    audio = await run_mlx(self._engine.synthesize, chunk.text, voice, self._speed)
                    pcm = to_pcm(audio)
                    self._cache.put(voice, self._speed, chunk.text, pcm)
                if waiting:
                    await self.stop_ttfb_metrics()
                    waiting = False
                for frame in self._frames(pcm, context_id):
                    yield frame
                if chunk.pause_s:
                    for frame in self._silence(chunk.pause_s, context_id):
                        yield frame
        finally:
            if waiting:
                await self.stop_ttfb_metrics()

    def _frames(self, pcm: bytes, context_id: str) -> Iterator[TTSAudioRawFrame]:
        step = int(self.sample_rate * CHUNK_SECONDS) * 2  # 16-bit samples
        for start in range(0, len(pcm), step):
            yield TTSAudioRawFrame(
                audio=pcm[start : start + step],
                sample_rate=self.sample_rate,
                num_channels=1,
                context_id=context_id,
            )

    def _silence(self, seconds: float, context_id: str) -> Iterator[TTSAudioRawFrame]:
        return self._frames(bytes(int(self.sample_rate * seconds) * 2), context_id)
