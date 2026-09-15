"""Automated caller: phone the running agent over WebRTC and measure real turn latency.

This is the Phase 1 latency gate. A Python WebRTC client connects to the agent exactly like
the browser page does, speaks synthesised caller lines, listens to the agent's audio, and times
each turn from the last sample of the caller's speech to the first audible sample of the reply.
That interval contains everything a caller waits for: WebRTC buffering both ways, the silence
wait, turn detection, transcription, routing, Gemma, the bank, Kokoro and playback.

Caller lines come from the dev and test benchmark conversations. They are rendered to WAV files
before any call starts (in an American voice, so they're never mistaken for the agent), so the
caller never competes with the agent for the GPU during a measured turn.

Usage (with ``python -m tellerline.agent`` running):
    python -m bench.caller --turns 20          # pilot
    python -m bench.caller --turns 220         # latency gate: 200+ turns
"""

import argparse
import asyncio
import fractions
import hashlib
import re
import time
from collections import deque
from dataclasses import dataclass, field

import av
import httpx
import numpy as np
import soundfile as sf
import soxr
from aiortc import MediaStreamError, MediaStreamTrack, RTCPeerConnection, RTCSessionDescription

from bench.common import RESULTS_DIR, ResultWriter, ms, summarize
from bench.dialogues import conversations
from tellerline.config import KOKORO_MLX_MODELS, LATENCY_TARGET_P90_S, TTS_MLX_VARIANT

RATE = 48_000
FRAME = 960  # 20 ms at 48 kHz
SPEECH_RMS = 0.01  # about -40 dBFS; Kokoro speech sits well above, WebRTC silence well below
BOT_DONE_SILENCE_S = 1.2
CALLER_PAUSE_S = 0.5
REPLY_TIMEOUT_S = 12.0
AUDIO_CACHE = RESULTS_DIR / "caller_audio"
CALLER_VOICES = ("am_michael", "af_heart")
VERIFY_LINE = "My customer number is 45127890 and my date of birth is the 3rd of March 1991."


# ---------------------------------------------------------------- call scripts


def call_scripts(max_turns: int) -> list[list[str]]:
    """Calls made of benchmark caller lines, repeated until ``max_turns`` is reached.

    Verified conversations start with a verification line. Lines that end a call (goodbye,
    asking for a person) only ever come last in a call.
    """
    enders = {"closing", "handoff"}
    calls: list[list[str]] = []
    for split in ("dev", "test"):
        convs = conversations(split)
        multi = [c for c in convs if c["kind"] == "multi"]
        single = [c for c in convs if c["kind"] == "single"]
        for dialogue in multi:
            lines = [t["user"] for t in dialogue["turns"]]
            calls.append(([VERIFY_LINE] if dialogue["verified"] else []) + lines)
        verified = [c["turns"][0] for c in single if c["verified"]]
        middle = [t["user"] for t in verified if t["category"] not in enders]
        last = [t["user"] for t in verified if t["category"] in enders]
        for start in range(0, len(middle), 6):
            call = [VERIFY_LINE, *middle[start : start + 6]]
            if last:
                call.append(last.pop())
            calls.append(call)
        for case in (c["turns"][0] for c in single if not c["verified"]):
            calls.append([case["user"]])

    scripts, total = [], 0
    while total < max_turns:
        for call in calls:
            if total >= max_turns:
                break
            call = call[: max_turns - total]
            scripts.append(call)
            total += len(call)
    return scripts


def _spell(digits: str) -> str:
    return " ".join(digits)


def as_spoken(line: str) -> str:
    """How a caller actually says numbers: customer and card numbers digit by digit.

    Text-to-speech reads "48210573" as "forty-eight million...", which no caller says and which
    is full of pauses. Years and amounts are left alone.
    """
    line = re.sub(r"\b(\d{4}) (\d{4})\b", lambda m: _spell(m[1] + m[2]), line)
    line = re.sub(r"\b\d{5,}\b", lambda m: _spell(m[0]), line)
    return re.sub(
        r"(?i)\b(ending(?: in)?|ends(?: in)?|card)\s+(\d{4})\b",
        lambda m: f"{m[1]} {_spell(m[2])}",
        line,
    )


def render_lines(lines: set[str]) -> dict[str, np.ndarray]:
    """48 kHz int16 audio per caller line, cached on disk; loads Kokoro only when needed."""
    AUDIO_CACHE.mkdir(parents=True, exist_ok=True)
    audio, missing = {}, []
    for index, line in enumerate(sorted(lines)):
        voice = CALLER_VOICES[index % len(CALLER_VOICES)]
        spoken = as_spoken(line)
        path = AUDIO_CACHE / f"{hashlib.sha1(f'{voice}|{spoken}'.encode()).hexdigest()[:16]}.wav"
        if path.exists():
            audio[line] = sf.read(path, dtype="int16")[0]
        else:
            missing.append((line, spoken, voice, path))
    if missing:
        from tellerline.tts.kokoro_mlx import SAMPLE_RATE, KokoroMLX

        kokoro = KokoroMLX(KOKORO_MLX_MODELS[TTS_MLX_VARIANT], "en-us")
        for line, spoken, voice, path in missing:
            samples = soxr.resample(kokoro.synthesize(spoken, voice), SAMPLE_RATE, RATE)
            pcm = (np.clip(samples, -1, 1) * 32767).astype(np.int16)
            sf.write(path, pcm, RATE)
            audio[line] = pcm
    return audio


# ---------------------------------------------------------------- WebRTC client


class CallerTrack(MediaStreamTrack):
    """Microphone stand-in: silence, except while speaking a queued line, paced in real time."""

    kind = "audio"

    def __init__(self):
        super().__init__()
        self._pts = 0
        self._start: float | None = None
        self._pending: deque[np.ndarray] = deque()
        self._done: asyncio.Future | None = None

    def say(self, pcm: np.ndarray) -> asyncio.Future:
        """Queue a line; the future resolves with the time its last sample went out."""
        chunks = [pcm[i : i + FRAME] for i in range(0, len(pcm), FRAME)]
        if len(chunks[-1]) < FRAME:
            chunks[-1] = np.pad(chunks[-1], (0, FRAME - len(chunks[-1])))
        self._pending.extend(chunks)
        self._done = asyncio.get_running_loop().create_future()
        return self._done

    async def recv(self) -> av.AudioFrame:
        if self._start is None:
            self._start = time.perf_counter()
        wait = self._start + self._pts / RATE - time.perf_counter()
        if wait > 0:
            await asyncio.sleep(wait)
        if self._pending:
            chunk = self._pending.popleft()
            if not self._pending and self._done and not self._done.done():
                self._done.set_result(time.perf_counter())
        else:
            chunk = np.zeros(FRAME, dtype=np.int16)
        frame = av.AudioFrame.from_ndarray(chunk.reshape(1, -1), format="s16", layout="mono")
        frame.sample_rate = RATE
        frame.pts = self._pts
        frame.time_base = fractions.Fraction(1, RATE)
        self._pts += FRAME
        return frame


@dataclass
class BotEar:
    """Tracks when the agent's audio becomes audible and when it has gone quiet."""

    last_sound: float = 0.0
    onsets: list[float] = field(default_factory=list)
    ended: bool = False
    _loud: bool = False

    async def listen(self, track: MediaStreamTrack) -> None:
        try:
            while True:
                frame = await track.recv()
                samples = frame.to_ndarray().astype(np.float32) / 32768.0
                now = time.perf_counter()
                if float(np.sqrt(np.mean(samples**2))) >= SPEECH_RMS:
                    if not self._loud:
                        self.onsets.append(now)
                    self._loud = True
                    self.last_sound = now
                elif now - self.last_sound > 0.3:
                    self._loud = False
        except MediaStreamError:
            self.ended = True

    async def wait_onset_after(self, t: float, timeout: float) -> float | None:
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline and not self.ended:
            for onset in self.onsets:
                if onset > t:
                    return onset
            await asyncio.sleep(0.005)
        return None

    async def wait_quiet(self, silence: float, timeout: float = 60.0) -> None:
        deadline = time.perf_counter() + timeout
        while time.perf_counter() < deadline and not self.ended:
            if self.last_sound and time.perf_counter() - self.last_sound >= silence:
                return
            await asyncio.sleep(0.02)


async def place_call(url: str, lines: list[str], audio: dict[str, np.ndarray]) -> list[dict]:
    pc = RTCPeerConnection()
    pc.createDataChannel("chat")
    caller = CallerTrack()
    pc.addTrack(caller)
    pc.addTransceiver("video", direction="recvonly")
    ear = BotEar()
    listening: list[asyncio.Task] = []

    @pc.on("track")
    def on_track(track):
        if track.kind == "audio":
            listening.append(asyncio.ensure_future(ear.listen(track)))

    await pc.setLocalDescription(await pc.createOffer())
    async with httpx.AsyncClient(timeout=30) as http:
        response = await http.post(
            f"{url}/api/offer", json={"sdp": pc.localDescription.sdp, "type": "offer"}
        )
        response.raise_for_status()
        answer = response.json()
    await pc.setRemoteDescription(RTCSessionDescription(sdp=answer["sdp"], type=answer["type"]))

    turns = []
    try:
        # The greeting.
        if await ear.wait_onset_after(0.0, timeout=30) is None:
            raise TimeoutError("The agent never greeted the caller")
        await ear.wait_quiet(BOT_DONE_SILENCE_S)

        for index, line in enumerate(lines):
            if ear.ended or pc.connectionState in ("closed", "failed"):
                break
            await asyncio.sleep(CALLER_PAUSE_S)
            try:
                # If the agent hangs up, nobody reads the microphone track any more.
                speech_end = await asyncio.wait_for(
                    caller.say(audio[line]), timeout=len(audio[line]) / RATE + 3.0
                )
            except TimeoutError:
                break
            onset = await ear.wait_onset_after(speech_end, REPLY_TIMEOUT_S)
            turns.append(
                {
                    "turn": index,
                    "caller": line,
                    "caller_speech_s": len(audio[line]) / RATE,
                    "latency_s": None if onset is None else onset - speech_end,
                }
            )
            if onset is None:
                break
            await ear.wait_quiet(BOT_DONE_SILENCE_S)
    finally:
        for task in listening:
            task.cancel()
        await pc.close()
    return turns


# ---------------------------------------------------------------- main


async def run(args: argparse.Namespace) -> None:
    scripts = call_scripts(args.turns)
    audio = render_lines({line for call in scripts for line in call})
    latencies: list[float] = []
    timeouts = 0
    config = {"url": args.url, "turns": args.turns, "calls": len(scripts)}
    with ResultWriter("caller", config) as writer:
        for number, lines in enumerate(scripts, start=1):
            try:
                turns = await place_call(args.url, lines, audio)
            except Exception as error:
                print(f"call {number}/{len(scripts)} failed: {type(error).__name__}: {error}")
                continue
            for turn in turns:
                writer.sample(call=number, **turn)
                if turn["latency_s"] is None:
                    timeouts += 1
                else:
                    latencies.append(turn["latency_s"])
            done = [t["latency_s"] for t in turns if t["latency_s"] is not None]
            print(
                f"call {number}/{len(scripts)}: {len(done)}/{len(lines)} turns, "
                f"latencies {[round(v * 1000) for v in done]} ms"
            )
            await asyncio.sleep(1.0)
        stats = summarize(latencies)
        passed = bool(latencies) and stats["p90"] <= LATENCY_TARGET_P90_S
        writer.summary(
            latency_s=stats, timeouts=timeouts, target_p90_s=LATENCY_TARGET_P90_S, passed=passed
        )

    print(
        f"\n{stats['n']} turns measured, {timeouts} without a reply: p50 {ms(stats['p50'])} ms, "
        f"p90 {ms(stats['p90'])} ms, p95 {ms(stats['p95'])} ms -> "
        f"{'within' if passed else 'over'} the {LATENCY_TARGET_P90_S} s p90 target"
    )
    print(f"Results: {writer.path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--url", default="http://localhost:7860")
    parser.add_argument("--turns", type=int, default=220)
    asyncio.run(run(parser.parse_args()))


if __name__ == "__main__":
    main()
