import time

import numpy as np
from pipecat.audio.vad.vad_analyzer import VADParams, VADState

from tellerline.audio.vad import CallerVAD

PARAMS = VADParams(confidence=0.8, start_secs=0.3, stop_secs=0.2)


def make_vad(**kwargs) -> CallerVAD:
    vad = CallerVAD(params=PARAMS, **kwargs)
    vad.set_sample_rate(16_000)
    vad.voice = False  # what Silero hears (patch_silero)
    return vad


def tone(dbfs: float, seconds: float = 0.02) -> bytes:
    """Noise at `dbfs` RMS, in one 20 ms chunk as the transport delivers it."""
    rng = np.random.default_rng(0)
    samples = rng.standard_normal(int(16_000 * seconds)) * 32768 * 10 ** (dbfs / 20)
    return np.clip(samples, -32768, 32767).astype(np.int16).tobytes()


async def feed(vad: CallerVAD, chunk: bytes, seconds: float) -> VADState:
    state = VADState.QUIET
    for _ in range(round(seconds / 0.02)):
        state = await vad.analyze_audio(chunk)
    return state


def patch_silero(monkeypatch):
    """Silero's verdict replaced by the VAD's `voice` switch: audio of any level, voice or not."""
    from pipecat.audio.vad.silero import SileroVADAnalyzer

    monkeypatch.setattr(
        SileroVADAnalyzer, "voice_confidence", lambda self, buffer: 1.0 if self.voice else 0.0
    )


async def test_the_vad_hears_the_caller_before_it_confirms_speech(monkeypatch):
    patch_silero(monkeypatch)
    vad = make_vad()
    await feed(vad, tone(-30), 0.2)
    assert not vad.hears_caller() and vad.heard_since() is None

    vad.voice = True
    before = time.time()
    assert await feed(vad, tone(-30), 0.06) == VADState.STARTING  # not yet confirmed...
    assert vad.hears_caller()  # ...but heard
    first_heard = vad.heard_since()
    assert before <= first_heard <= time.time()
    assert await feed(vad, tone(-30), 0.4) == VADState.SPEAKING
    assert vad.heard_since() == first_heard

    vad.voice = False
    assert await feed(vad, tone(-30), 0.4) == VADState.QUIET
    assert not vad.hears_caller() and vad.heard_since() is None


async def test_nothing_quieter_than_the_floor_is_the_caller(monkeypatch):
    patch_silero(monkeypatch)
    vad = make_vad()
    vad.voice = True
    assert await feed(vad, tone(-55), 1.0) == VADState.QUIET
    assert await feed(vad, tone(-35), 0.5) == VADState.SPEAKING


async def test_once_the_caller_is_known_the_room_well_below_them_is_not_them(monkeypatch):
    patch_silero(monkeypatch)
    vad = make_vad()
    vad.voice = True
    await feed(vad, tone(-25), 2.0)  # the caller, talking
    assert abs(vad.threshold_dbfs() - -37.0) < 0.5  # the caller's level, less 12 dB
    vad.voice = False
    await feed(vad, tone(-25), 0.5)
    # A voice in the room, 15 dB below the caller: Silero hears speech, the VAD doesn't.
    vad.voice = True
    assert await feed(vad, tone(-40), 1.0) == VADState.QUIET
    # The caller, a little quieter than before: still them.
    assert await feed(vad, tone(-32), 0.5) == VADState.SPEAKING


async def test_the_agents_own_voice_does_not_teach_the_callers_level(monkeypatch):
    patch_silero(monkeypatch)
    vad = make_vad()
    vad.set_agent_speaking(True)
    vad.voice = True
    await feed(vad, tone(-20), 2.0)
    assert vad.threshold_dbfs() == -45.0  # still only the floor


async def test_without_the_caller_gate_pipecats_volume_threshold_applies(monkeypatch):
    patch_silero(monkeypatch)
    vad = make_vad(caller_gate=False)
    assert vad.params.min_volume == PARAMS.min_volume
    vad.voice = True
    assert await feed(vad, tone(-80), 1.0) == VADState.QUIET
