import numpy as np
from pipecat.frames.frames import TranscriptionFrame, TTSAudioRawFrame, TTSSpeakFrame
from pipecat.tests.utils import run_test

from tellerline.services.stt import ParakeetMLXSTTService
from tellerline.services.tts import KokoroMLXTTSService


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


async def test_tts_speaks_in_short_chunks_with_the_chosen_voice():
    engine = FakeSynthesizer(seconds=0.35)
    tts = KokoroMLXTTSService(voice="bm_george", loader=lambda _: engine)
    down, _ = await run_test(tts, frames_to_send=[TTSSpeakFrame("Your card is now frozen.")])

    audio = [f for f in down if isinstance(f, TTSAudioRawFrame)]
    assert [len(f.audio) for f in audio] == [4800, 4800, 4800, 2400]  # 0.1 s chunks of 16-bit audio
    assert all(f.sample_rate == 24_000 for f in audio)
    assert int(np.frombuffer(audio[0].audio, dtype=np.int16)[0]) == int(0.5 * 32767)
    assert ("Your card is now frozen.", "bm_george") in engine.calls


async def test_stt_turns_pcm_into_a_transcription():
    model = FakeTranscriber("What's my balance?")
    stt = ParakeetMLXSTTService(loader=lambda _: model, sample_rate=16_000)
    await run_test(stt, frames_to_send=[])  # start() loads and warms up the model

    frames = [frame async for frame in stt.run_stt(np.zeros(8_000, dtype=np.int16).tobytes())]
    assert isinstance(frames[0], TranscriptionFrame)
    assert frames[0].text == "What's my balance?"
    assert model.lengths[-1] == 8_000


async def test_stt_resamples_other_rates_to_16k():
    model = FakeTranscriber("hello")
    stt = ParakeetMLXSTTService(loader=lambda _: model, sample_rate=8_000)
    await run_test(stt, frames_to_send=[])
    [frame async for frame in stt.run_stt(np.zeros(8_000, dtype=np.int16).tobytes())]
    assert abs(model.lengths[-1] - 16_000) <= 2
