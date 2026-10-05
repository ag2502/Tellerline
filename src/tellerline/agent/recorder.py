"""A call's timeline: what happened in each turn, how long each stage took, and both voices.

Every call keeps a timeline. Each turn's record (what speech recognition heard, the exact text
the model read, the route, the model's answer, what the bank did and what the caller heard) is
sent to the call page as it happens, which is what the page's glass-box view shows.

With recording on (``TELLERLINE_RECORD=1``) the timeline is also saved with both voices, on
separate tracks that share one clock, under ``results/recordings/<call id>/``:

- ``call.json``: the turns, speaking events and per-turn latency, times in seconds from the
  start of the audio;
- ``caller.wav`` and ``agent.wav``: 16-bit mono, the same length, so they line up.

``scripts/export_calls.py`` turns recordings into the website's call replays.
"""

import json
import time
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
)
from pipecat.observers.base_observer import BaseObserver, FramePushed
from pipecat.processors.audio.audio_buffer_processor import AudioBufferProcessor
from pipecat.processors.frame_processor import FrameDirection

from tellerline.agent.observability import RESULTS_DIR

RECORDINGS_DIR = RESULTS_DIR / "recordings"
_SPEAKING = {
    VADUserStartedSpeakingFrame: "caller_started",
    VADUserStoppedSpeakingFrame: "caller_stopped",
    BotStartedSpeakingFrame: "agent_started",
    BotStoppedSpeakingFrame: "agent_stopped",
}


@dataclass
class CallTimeline:
    """Everything that happened on one call, on one clock (``time.time()``)."""

    call_id: str
    started_at: float = field(default_factory=time.time)
    turns: list[dict[str, Any]] = field(default_factory=list)
    events: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    # Set by speech recognition when it finishes a transcript, read by the next turn.
    last_transcription_ms: float | None = None

    def at(self, moment: float | None = None) -> float:
        """Seconds since the call's clock started."""
        return round((moment if moment is not None else time.time()) - self.started_at, 3)

    def note_transcription(self, milliseconds: float) -> None:
        self.last_transcription_ms = round(milliseconds, 1)

    def event(self, kind: str, moment: float | None = None) -> None:
        self.events.append({"t": self.at(moment), "event": kind})

    def add_turn(self, record: dict[str, Any]) -> dict[str, Any]:
        """Number and timestamp a turn's record, attach the transcription time, keep it."""
        record = {
            "turn": len(self.turns) + 1,
            "t": self.at(),
            "stt_ms": self.last_transcription_ms,
            **record,
        }
        self.last_transcription_ms = None
        self.turns.append(record)
        return record

    def add_latency(self, seconds: float, breakdown: dict | None) -> dict[str, Any] | None:
        """Attach a measured reply latency to the latest turn that doesn't have one yet."""
        for record in reversed(self.turns):
            if "reply_s" in record:
                break
            record["reply_s"] = round(seconds, 3)
            record["stages_ms"] = stage_times(breakdown)
            return record
        return None

    def as_dict(self) -> dict[str, Any]:
        return {
            "call_id": self.call_id,
            "started_at": self.started_at,
            **self.metadata,
            "events": self.events,
            "turns": self.turns,
        }


def stage_times(breakdown: dict | None) -> dict[str, float]:
    """Pipecat's latency breakdown as milliseconds per named stage."""
    if not breakdown:
        return {}
    stages = {
        part["key"]: round(part["duration_secs"] * 1000, 1)
        for part in breakdown.get("contributions", [])
        if part.get("key") not in ("pipeline", "first_request")
    }
    if breakdown.get("user_turn_secs") is not None:
        stages["turn_end"] = round(breakdown["user_turn_secs"] * 1000, 1)
    return stages


class TimelineObserver(BaseObserver):
    """Writes when the caller and the agent start and stop speaking into the timeline."""

    def __init__(self, timeline: CallTimeline, **kwargs):
        super().__init__(**kwargs)
        self._timeline = timeline
        self._seen: set[int] = set()

    async def on_push_frame(self, data: FramePushed):
        kind = _SPEAKING.get(type(data.frame))
        if kind is None or data.frame.id in self._seen:
            return
        if data.direction != FrameDirection.DOWNSTREAM and data.frame.broadcast_sibling_id:
            return
        self._seen.add(data.frame.id)
        self._timeline.event(kind)


class CallRecorder:
    """Records both voices and saves them with the timeline when the call ends."""

    def __init__(self, timeline: CallTimeline, directory: Path = RECORDINGS_DIR):
        self.timeline = timeline
        self.directory = directory / timeline.call_id
        self.processor = AudioBufferProcessor(num_channels=1, auto_start_recording=True)
        self._caller = b""
        self._agent = b""
        self._sample_rate = 0

        @self.processor.event_handler("on_recording_started")
        async def on_started(_):
            # The audio's first sample is time zero for everything saved with it.
            now = time.time()
            shift = now - self.timeline.started_at
            self.timeline.started_at = now
            for item in self.timeline.events + self.timeline.turns:
                item["t"] = round(item["t"] - shift, 3)

        @self.processor.event_handler("on_track_audio_data")
        async def on_tracks(_, caller: bytes, agent: bytes, sample_rate: int, num_channels: int):
            self._caller += caller
            self._agent += agent
            self._sample_rate = sample_rate

    async def save(self) -> Path | None:
        """Write call.json, caller.wav and agent.wav; returns the folder, or None if silent."""
        await self.processor.stop_recording()
        if not self.timeline.turns and not self._agent:
            return None
        self.directory.mkdir(parents=True, exist_ok=True)
        length = max(len(self._caller), len(self._agent))
        for name, audio in (("caller", self._caller), ("agent", self._agent)):
            with wave.open(str(self.directory / f"{name}.wav"), "wb") as file:
                file.setnchannels(1)
                file.setsampwidth(2)
                file.setframerate(self._sample_rate or 16_000)
                file.writeframes(audio + bytes(length - len(audio)))
        record = {**self.timeline.as_dict(), "sample_rate": self._sample_rate}
        (self.directory / "call.json").write_text(json.dumps(record, indent=1, ensure_ascii=False))
        return self.directory
