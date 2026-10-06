import numpy as np
from pipecat.frames.frames import (
    TranscriptionFrame,
    TTSAudioRawFrame,
    TTSSpeakFrame,
)
from pipecat.tests.utils import run_test

from tellerline.services.stt import ParakeetMLXSTTService
from tellerline.services.tts import KokoroMLXTTSService, PhraseCache, warm_phrases
from tellerline.tts.chunks import CLAUSE_PAUSES_S


class FakeSynthesizer:
    def __init__(self, seconds: float = 0.35):
        self.seconds = seconds
        self.calls: list[tuple[str, str]] = []

    def synthesize(self, text: str, voice: str, speed: float = 1.0) -> np.ndarray:
        self.calls.append((text, voice))
        return np.full(int(24_000 * self.seconds), 0.5, dtype=np.float32)


class FakeTranscriber:
    def __init__(self, text: str):
        self.text = text
        self.lengths: list[int] = []

    def generate(self, audio):
        self.lengths.append(audio.shape[0])
        return type("Result", (), {"text": self.text})()


class Saying(FakeTranscriber):
    """Transcribes each segment as the next of `texts`; the last one for everything after."""

    def __init__(self, *texts: str):
        super().__init__(texts[-1])
        self.texts = list(texts)

    def generate(self, audio):
        self.lengths.append(audio.shape[0])
        text = self.texts.pop(0) if len(self.texts) > 1 else self.texts[0]
        return type("Result", (), {"text": text})()


async def test_tts_speaks_in_short_chunks_with_the_chosen_voice():
    engine = FakeSynthesizer(seconds=0.35)
    tts = KokoroMLXTTSService(voice="bm_george", loader=lambda _: engine, cache=PhraseCache())
    down, _ = await run_test(tts, frames_to_send=[TTSSpeakFrame("Your card is now frozen.")])

    audio = [f for f in down if isinstance(f, TTSAudioRawFrame)]
    assert [len(f.audio) for f in audio] == [4800, 4800, 4800, 2400]  # 0.1 s chunks of 16-bit audio
    assert all(f.sample_rate == 24_000 for f in audio)
    assert int(np.frombuffer(audio[0].audio, dtype=np.int16)[0]) == int(0.5 * 32767)
    assert ("Your card is now frozen.", "bm_george") in engine.calls


async def test_tts_renders_clause_by_clause_with_pauses_between():
    engine = FakeSynthesizer(seconds=0.2)
    tts = KokoroMLXTTSService(loader=lambda _: engine, cache=PhraseCache())
    down, _ = await run_test(
        tts, frames_to_send=[TTSSpeakFrame("On your current account, the balance is ten euro.")]
    )

    assert [text for text, _ in engine.calls] == [
        "On your current account,",
        "the balance is ten euro.",
    ]
    samples = np.concatenate(
        [np.frombuffer(f.audio, dtype=np.int16) for f in down if isinstance(f, TTSAudioRawFrame)]
    )
    rate = 24_000
    speech = int(0.2 * rate)
    pause = int(CLAUSE_PAUSES_S[","] * rate)
    assert len(samples) == 2 * speech + pause
    assert not samples[speech : speech + pause].any()  # the comma's pause is silence


async def test_tts_reuses_cached_clauses():
    engine = FakeSynthesizer(seconds=0.1)
    cache = PhraseCache()
    warm_phrases(engine, ["I've frozen that card for you."], voice="bf_emma", cache=cache)
    assert len(engine.calls) == 1

    tts = KokoroMLXTTSService(voice="bf_emma", loader=lambda _: engine, cache=cache)
    await run_test(tts, frames_to_send=[TTSSpeakFrame("I've frozen that card for you.")])
    assert len(engine.calls) == 1  # spoken from the cache, not rendered again
    assert cache.hits >= 1


def test_phrase_cache_drops_the_least_recently_used():
    cache = PhraseCache(max_entries=2)
    cache.put("v", 1.0, "a", b"a")
    cache.put("v", 1.0, "b", b"b")
    assert cache.get("v", 1.0, "a") == b"a"  # "a" is now the most recent
    cache.put("v", 1.0, "c", b"c")
    assert cache.get("v", 1.0, "b") is None
    assert cache.get("v", 1.0, "a") == b"a"
    assert len(cache) == 2


async def test_stt_turns_pcm_into_a_transcription():
    model = FakeTranscriber("What's my balance on 1,234?")
    stt = ParakeetMLXSTTService(loader=lambda _: model, sample_rate=16_000)
    await run_test(stt, frames_to_send=[])  # start() loads and warms up the model

    frames = [frame async for frame in stt.run_stt(np.zeros(8_000, dtype=np.int16).tobytes())]
    assert isinstance(frames[0], TranscriptionFrame)
    assert frames[0].text == "What's my balance on 1234?"
    assert model.lengths[-1] == 8_000


async def test_stt_resamples_other_rates_to_16k():
    model = FakeTranscriber("hello")
    stt = ParakeetMLXSTTService(loader=lambda _: model, sample_rate=8_000)
    await run_test(stt, frames_to_send=[])
    [frame async for frame in stt.run_stt(np.zeros(8_000, dtype=np.int16).tobytes())]
    assert abs(model.lengths[-1] - 16_000) <= 2


async def test_a_turn_in_several_segments_is_transcribed_whole():
    model = Saying(
        "four five one two", "seven. eight nine zero", "four five one two seven eight nine zero"
    )
    stt = ParakeetMLXSTTService(loader=lambda _: model, sample_rate=16_000)
    await run_test(stt, frames_to_send=[])
    padding = 8_000  # the 0.5 s of silence Pipecat pads each segment with
    one = np.zeros(16_000 + padding, dtype=np.int16).tobytes()
    two = np.zeros(24_000 + padding, dtype=np.int16).tobytes()

    [frame async for frame in stt.run_stt(one)]
    # One segment: its own transcript stands.
    assert await stt.turn_transcript("four five one two") is None
    [frame async for frame in stt.run_stt(two)]
    turn = "four five one two seven. eight nine zero"
    assert await stt.turn_transcript(turn) == "four five one two seven eight nine zero"
    # Both segments as said, without their padding, then the padding once at the end.
    assert model.lengths[-1] == 16_000 + 24_000 + padding


async def test_the_turn_is_the_segments_behind_its_words():
    # An earlier turn's segment stays out, even when the agent's reply in between was dropped
    # and the caller's turn spans two segments around it.
    model = Saying(
        "Hello.", "Pause my card ending 7780 for a bit.", "It's somewhere in the house.", "whole"
    )
    stt = ParakeetMLXSTTService(loader=lambda _: model, sample_rate=16_000)
    await run_test(stt, frames_to_send=[])
    for seconds in (1, 2, 3):
        [
            frame
            async for frame in stt.run_stt(np.zeros(16_000 * seconds + 8_000, np.int16).tobytes())
        ]
    turn = "Pause my card ending 7780 for a bit. It's somewhere in the house."
    assert await stt.turn_transcript(turn) == "whole"
    assert model.lengths[-1] == 16_000 * (2 + 3) + 8_000


async def test_words_that_arent_the_latest_segments_are_left_as_they_are():
    model = Saying("Freeze my card.", "It ends 4217.")
    stt = ParakeetMLXSTTService(loader=lambda _: model, sample_rate=16_000)
    await run_test(stt, frames_to_send=[])
    for _ in range(2):
        [frame async for frame in stt.run_stt(np.zeros(24_000, np.int16).tobytes())]
    assert await stt.turn_transcript("Unfreeze my card. It ends 4217.") is None
    assert await stt.turn_transcript("It ends 4217.") is None  # one segment


async def test_a_noise_after_the_turn_is_left_out():
    model = Saying("My card", "ends 4217.", "", "My card ends 4217.")
    stt = ParakeetMLXSTTService(loader=lambda _: model, sample_rate=16_000)
    await run_test(stt, frames_to_send=[])
    for seconds in (1, 2, 3):
        [
            frame
            async for frame in stt.run_stt(np.zeros(16_000 * seconds + 8_000, np.int16).tobytes())
        ]
    assert await stt.turn_transcript("My card ends 4217.") == "My card ends 4217."
    assert model.lengths[-1] == 16_000 * (1 + 2) + 8_000


async def test_two_seconds_before_speech_is_confirmed_are_kept():
    from pipecat.frames.frames import InputAudioRawFrame

    model = FakeTranscriber("hello")
    stt = ParakeetMLXSTTService(loader=lambda _: model, sample_rate=16_000)
    await run_test(stt, frames_to_send=[])
    second = InputAudioRawFrame(np.zeros(16_000, dtype=np.int16).tobytes(), 16_000, 1)
    for _ in range(4):
        await stt.process_audio_frame(second, None)
    assert len(stt._audio_buffer) == 2 * 16_000 * 2  # two seconds of 16-bit samples


def test_transcripts_lose_digit_group_commas():
    from tellerline.services.stt import clean_transcript

    assert (
        clean_transcript("My customer number is 45,127,890.") == "My customer number is 45127890."
    )
    assert clean_transcript("It cost 1,250 euro, thanks") == "It cost 1250 euro, thanks"
    assert clean_transcript("Yes, 12, 13") == "Yes, 12, 13"


async def test_mlx_work_runs_most_urgent_first():
    import asyncio
    import threading

    from tellerline.services.mlx_thread import Priority, run_mlx

    gate, order = threading.Event(), []
    blocker = asyncio.ensure_future(run_mlx(gate.wait, priority=Priority.TRANSCRIBE))
    await asyncio.sleep(0.05)  # the worker is now busy, so the next three queue up
    later = asyncio.ensure_future(run_mlx(order.append, "later", priority=Priority.LATER_AUDIO))
    first = asyncio.ensure_future(run_mlx(order.append, "first", priority=Priority.FIRST_AUDIO))
    stt = asyncio.ensure_future(run_mlx(order.append, "stt", priority=Priority.TRANSCRIBE))
    await asyncio.sleep(0.05)
    gate.set()
    await asyncio.gather(blocker, later, first, stt)
    assert order == ["stt", "first", "later"]
