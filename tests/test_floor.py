import time

from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    InterruptionFrame,
    TextFrame,
    TTSAudioRawFrame,
)
from pipecat.tests.utils import SleepFrame, run_test

from tellerline.agent.floor import FloorGate


def audio(byte: int = 1) -> TTSAudioRawFrame:
    return TTSAudioRawFrame(audio=bytes([byte]) * 640, sample_rate=16_000, num_channels=1)


def said(frames) -> list:
    """What reached the line, in order: audio by its first byte, text by its words."""
    return [
        f.audio[0] if isinstance(f, TTSAudioRawFrame) else f.text
        for f in frames
        if isinstance(f, (TTSAudioRawFrame, TextFrame))
    ]


def heard_for(seconds: float):
    """A caller the VAD hears for `seconds` from the first time it's asked."""
    started = []

    def hears_caller() -> bool:
        started.append(started[0] if started else time.monotonic())
        return time.monotonic() - started[0] < seconds

    return hears_caller


async def test_a_reply_goes_straight_out_when_the_caller_is_silent():
    gate = FloorGate(lambda: False)
    down, _ = await run_test(gate, frames_to_send=[audio(1), TextFrame("Hello."), audio(2)])
    assert said(down) == [1, "Hello.", 2]


async def test_a_reply_waits_while_the_caller_can_be_heard_then_goes_out_in_order():
    gate = FloorGate(heard_for(0.1), quiet_s=0.02, max_hold_s=1.0)
    started = time.monotonic()
    frames = [audio(1), TextFrame("Sorry,"), audio(2), SleepFrame(0.3)]
    down, _ = await run_test(gate, frames_to_send=frames)
    assert said(down) == [1, "Sorry,", 2]
    assert time.monotonic() - started >= 0.12


async def test_a_caller_who_takes_the_turn_back_hears_none_of_the_reply():
    gate = FloorGate(lambda: True, max_hold_s=5.0)
    frames = [audio(1), TextFrame("Sorry,"), SleepFrame(0.05), InterruptionFrame(), audio(3)]
    down, _ = await run_test(gate, frames_to_send=frames)
    # The reply was dropped; what follows the interruption is a new reply, and waits again.
    assert 1 not in said(down) and "Sorry," not in said(down)
    assert any(isinstance(f, InterruptionFrame) for f in down)


async def test_a_reply_waits_no_longer_than_the_hold_allows():
    gate = FloorGate(lambda: True, max_hold_s=0.05)
    down, _ = await run_test(gate, frames_to_send=[audio(1), audio(2), SleepFrame(0.2)])
    assert said(down) == [1, 2]


async def test_once_the_agent_is_talking_its_audio_is_not_held():
    # Interrupting a reply under way takes words (tellerline.agent.turns), not just a sound.
    gate = FloorGate(lambda: True, max_hold_s=5.0)
    frames = [BotStartedSpeakingFrame(), audio(1), SleepFrame(0.05), InterruptionFrame()]
    down, _ = await run_test(gate, frames_to_send=frames)
    assert said(down) == [1]


async def test_the_vad_is_told_when_the_agent_talks():
    told = []
    gate = FloorGate(lambda: False, agent_speaking=told.append)
    await run_test(gate, frames_to_send=[BotStartedSpeakingFrame(), audio(1)])
    assert told == [True]
