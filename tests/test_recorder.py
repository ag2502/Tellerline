import json
import wave

from tellerline.agent.recorder import CallRecorder, CallTimeline, stage_times


def test_turns_are_numbered_and_carry_the_transcription_time():
    timeline = CallTimeline("call-test", started_at=100.0)
    timeline.note_transcription(61.23)
    first = timeline.add_turn({"heard": "hello"})
    second = timeline.add_turn({"heard": "again"})
    assert first["turn"] == 1 and first["stt_ms"] == 61.2
    assert second["turn"] == 2 and second["stt_ms"] is None  # used once, then cleared


def test_latency_attaches_to_the_latest_turn_without_one():
    timeline = CallTimeline("call-test")
    timeline.add_turn({"heard": "one"})
    record = timeline.add_latency(1.2345, None)
    assert record["turn"] == 1 and record["reply_s"] == 1.234
    assert timeline.add_latency(0.9, None) is None  # no newer turn waiting


def test_stage_times_name_each_part_of_the_wait():
    breakdown = {
        "contributions": [
            {"key": "first_request", "duration_secs": 22.1},
            {"key": "llm_inference", "duration_secs": 0.2567},
            {"key": "speech_synthesis", "duration_secs": 0.235},
            {"key": "pipeline", "duration_secs": 0.001},
        ],
        "user_turn_secs": 0.412,
    }
    assert stage_times(breakdown) == {
        "llm_inference": 256.7,
        "speech_synthesis": 235.0,
        "turn_end": 412.0,
    }
    assert stage_times(None) == {}


async def test_recordings_save_both_voices_on_one_clock(tmp_path):
    timeline = CallTimeline("call-test")
    timeline.add_turn({"heard": "hello", "spoken": "Hi"})
    recorder = CallRecorder(timeline, directory=tmp_path)
    handlers = recorder.processor._event_handlers["on_track_audio_data"].handlers
    caller, agent = bytes(3200), bytes(1600)  # 0.1 s and 0.05 s at 16 kHz
    for handler in handlers:
        await handler(recorder.processor, caller, agent, 16_000, 1)

    folder = await recorder.save()
    assert folder == tmp_path / "call-test"
    for name in ("caller", "agent"):
        with wave.open(str(folder / f"{name}.wav")) as file:
            assert file.getframerate() == 16_000
            assert file.getnframes() == 1600  # padded to the same length
    saved = json.loads((folder / "call.json").read_text())
    assert saved["call_id"] == "call-test" and saved["turns"][0]["heard"] == "hello"
