import json
from types import SimpleNamespace

import numpy as np
from pipecat.audio.dtmf.types import KeypadEntry
from pipecat.frames.frames import (
    EndFrame,
    InputAudioRawFrame,
    InputDTMFFrame,
    InputTransportMessageFrame,
    InterruptionFrame,
    OutputAudioRawFrame,
    TextFrame,
)

from tellerline.agent.phone import AsteriskSerializer, Pacer, parse_event

MEDIA_START = {
    "event": "MEDIA_START",
    "connection_id": "e226e283",
    "channel": "WebSocket/tellerline-00000001",
    "format": "slin16",
    "optimal_frame_size": 640,
    "ptime": 20,
}


async def serializer(rate: int = 16_000) -> AsteriskSerializer:
    serializer = AsteriskSerializer()
    await serializer.setup(SimpleNamespace(audio_in_sample_rate=rate))
    return serializer


def test_events_parse_in_both_formats():
    assert parse_event(json.dumps(MEDIA_START)) == MEDIA_START
    plain = parse_event("MEDIA_START connection_id:e226e283 format:slin16 ptime:20")
    assert plain == {
        "event": "MEDIA_START",
        "connection_id": "e226e283",
        "format": "slin16",
        "ptime": "20",
    }
    assert parse_event("") == {"event": ""}
    assert parse_event("{not json") == {}


async def test_media_start_connects_the_call_and_sets_the_command_format():
    started = []
    json_line = await serializer()

    async def on_media_start(event):
        started.append(event["channel"])

    json_line.on_media_start = on_media_start
    frame = await json_line.deserialize(json.dumps(MEDIA_START))
    assert isinstance(frame, InputTransportMessageFrame)
    assert frame.message["format"] == "slin16"
    assert started == ["WebSocket/tellerline-00000001"]
    assert json.loads(await json_line.serialize(EndFrame())) == {"command": "HANGUP"}
    assert json.loads(await json_line.serialize(InterruptionFrame())) == {"command": "FLUSH_MEDIA"}

    plain_line = await serializer()
    await plain_line.deserialize("MEDIA_START connection_id:e226e283 format:slin16 ptime:20")
    assert await plain_line.serialize(EndFrame()) == "HANGUP"


async def test_caller_audio_reaches_the_pipeline_at_its_rate():
    line = await serializer()
    pcm = (np.sin(np.arange(320) / 5) * 8000).astype(np.int16).tobytes()
    frame = await line.deserialize(pcm)
    assert isinstance(frame, InputAudioRawFrame)
    assert frame.sample_rate == 16_000
    assert frame.audio == pcm


async def test_agent_audio_is_resampled_to_the_channel_rate():
    line = await serializer()
    chunk = (np.sin(np.arange(960) / 7) * 8000).astype(np.int16).tobytes()  # 40 ms at 24 kHz
    sent = b""
    for _ in range(25):
        payload = await line.serialize(
            OutputAudioRawFrame(audio=chunk, sample_rate=24_000, num_channels=1)
        )
        sent += payload or b""
    # One second at 24 kHz becomes (close to) one second at 16 kHz, less the resampler's delay.
    assert 0.9 * 32_000 <= len(sent) <= 32_000


async def test_keypad_presses_become_dtmf_frames():
    line = await serializer()
    frame = await line.deserialize(json.dumps({"event": "DTMF_END", "digit": "5"}))
    assert isinstance(frame, InputDTMFFrame)
    assert frame.button == KeypadEntry.FIVE
    assert await line.deserialize(json.dumps({"event": "DTMF_END", "digit": "x"})) is None


async def test_other_frames_and_events_are_ignored():
    line = await serializer()
    assert await line.serialize(TextFrame("hello")) is None
    assert await line.deserialize(json.dumps({"event": "MEDIA_XON"})) is None


def test_the_pacer_keeps_the_audio_a_fixed_lead_ahead():
    pacer = Pacer(lead_s=0.2)
    # Five 40 ms chunks sent at once: the first 0.2 s go straight out...
    waits = [pacer.delay(now=10.0, chunk_s=0.04) for _ in range(5)]
    assert waits == [0.0, 0.0, 0.0, 0.0, 0.0]
    # ...and after that each chunk waits until the queue is back to 0.2 s.
    assert abs(pacer.delay(now=10.0, chunk_s=0.04) - 0.04) < 1e-9


def test_the_pacer_starts_afresh_after_a_pause_or_an_interruption():
    pacer = Pacer(lead_s=0.2)
    for _ in range(10):
        pacer.delay(now=10.0, chunk_s=0.04)
    assert pacer.delay(now=20.0, chunk_s=0.04) == 0.0  # long since played out
    for _ in range(10):
        pacer.delay(now=30.0, chunk_s=0.04)
    pacer.reset()
    assert pacer.delay(now=30.0, chunk_s=0.04) == 0.0
