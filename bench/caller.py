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
import json
import re
import subprocess
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

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
STAGGER_S = 2.7  # seconds between the first calls of concurrent lines
REPLY_TIMEOUT_S = 12.0
AUDIO_CACHE = RESULTS_DIR / "caller_audio"
CALLER_VOICES = ("am_michael", "af_heart")
KOKORO_US_VOICES = ("am_michael", "af_heart", "af_bella", "af_nicole", "am_adam", "am_eric")
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


def load_script(path: Path) -> list[dict]:
    """Scripted calls: a JSON list of {"name", "voice", "lines"}, each call in one voice."""
    calls = json.loads(path.read_text())
    for call in calls:
        assert call["voice"] in KOKORO_US_VOICES, f"{call['name']}: unknown voice {call['voice']}"
        assert call["lines"], f"{call['name']}: no lines"
    return calls


def render_lines(lines: set[str], voices: dict[str, str] | None = None) -> dict[str, np.ndarray]:
    """48 kHz int16 audio per caller line, cached on disk; loads Kokoro only when needed.

    Benchmark lines alternate between two American voices; scripted calls give each line its
    call's voice.
    """
    AUDIO_CACHE.mkdir(parents=True, exist_ok=True)
    audio, missing = {}, []
    for index, line in enumerate(sorted(lines)):
        voice = (voices or {}).get(line) or CALLER_VOICES[index % len(CALLER_VOICES)]
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


BACKGROUND_LINES = [
    ("am_adam", "Did you see the match last night? I couldn't believe that second goal."),
    ("af_sky", "We should book the restaurant for Friday before it fills up."),
    ("bm_daniel", "The train was delayed again this morning, I was nearly an hour late."),
    ("af_nicole", "Can you pass me the charger? My phone is almost dead."),
]


def render_background(level_db: float) -> np.ndarray:
    """A noisy room: overlapping background conversation plus steady noise, as a 20 s loop.

    ``level_db`` is the background's loudness relative to the caller's speech (e.g. -15 dB is a
    conversation a couple of metres away). Cached on disk like the caller's lines.
    """
    path = AUDIO_CACHE / f"background_{int(-level_db)}db.wav"
    if path.exists():
        return sf.read(path, dtype="int16")[0]
    from tellerline.tts.kokoro_mlx import SAMPLE_RATE, KokoroMLX

    kokoro = KokoroMLX(KOKORO_MLX_MODELS[TTS_MLX_VARIANT], "en-us")
    loop = np.zeros(RATE * 20, dtype=np.float32)
    rng = np.random.default_rng(7)
    for index, (voice, text) in enumerate(BACKGROUND_LINES * 2):
        speech = soxr.resample(kokoro.synthesize(text, voice), SAMPLE_RATE, RATE).astype(np.float32)
        start = (index * RATE * 2 + rng.integers(0, RATE)) % (len(loop) - len(speech))
        loop[start : start + len(speech)] += speech
    loop += 0.3 * np.std(loop) * rng.standard_normal(len(loop)).astype(np.float32)  # room noise
    speech_rms = 0.12  # typical RMS of the caller's rendered lines
    loop *= speech_rms * 10 ** (level_db / 20) / (np.sqrt(np.mean(loop**2)) + 1e-9)
    pcm = (np.clip(loop, -1, 1) * 32767).astype(np.int16)
    sf.write(path, pcm, RATE)
    return pcm


# ---------------------------------------------------------------- WebRTC client


class CallerTrack(MediaStreamTrack):
    """Microphone stand-in: silence, except while speaking a queued line, paced in real time."""

    kind = "audio"

    def __init__(self, background: np.ndarray | None = None):
        super().__init__()
        self._background = background
        self._background_pos = 0
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
        if self._background is not None:
            pos = self._background_pos
            noise = np.take(self._background, range(pos, pos + FRAME), mode="wrap")
            self._background_pos = (pos + FRAME) % len(self._background)
            chunk = np.clip(chunk.astype(np.int32) + noise, -32768, 32767).astype(np.int16)
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


async def place_call(
    url: str, lines: list[str], audio: dict[str, np.ndarray], background: np.ndarray | None = None
) -> list[dict]:
    pc = RTCPeerConnection()
    channel = pc.createDataChannel("chat")
    reports: list[dict] = []

    @channel.on("message")
    def on_message(message):
        # The agent's own account of each turn (tellerline.agent.recorder), kept with the
        # latency this caller measured.
        try:
            data = json.loads(message)
        except (TypeError, ValueError):
            return
        if data.get("type") == "server-message" and isinstance(data.get("data"), dict):
            reports.append(data["data"])

    caller = CallerTrack(background)
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
            seen = len(reports)
            speech_s = len(audio[line]) / RATE
            onset = await ear.wait_onset_after(speech_end, REPLY_TIMEOUT_S)
            # The agent started talking before the caller had finished (it answered at a pause
            # mid-sentence): there's no reply gap to measure, so the turn is counted apart.
            overlap = any(speech_end - speech_s + 0.3 < t < speech_end for t in ear.onsets)
            record = {
                "turn": index,
                "caller": line,
                "caller_speech_s": speech_s,
                "overlap": overlap,
                "latency_s": None if onset is None or overlap else onset - speech_end,
            }
            turns.append(record)
            if onset is None:
                break
            await ear.wait_quiet(BOT_DONE_SILENCE_S)
            record["agent"] = agent_report(reports[seen:])
    finally:
        for task in listening:
            task.cancel()
        await pc.close()
    return turns


def agent_report(messages: list[dict]) -> dict | None:
    """The agent's last turn report and its measured latency, from the messages of one turn."""
    turn = next((m for m in reversed(messages) if m.get("type") == "tellerline-turn"), None)
    if turn is None:
        return None
    latency = next(
        (
            m
            for m in messages
            if m.get("type") == "tellerline-latency" and m.get("turn") == turn.get("turn")
        ),
        {},
    )
    return {
        "heard": turn.get("heard"),
        "understood": turn.get("understood"),
        "skill": (turn.get("route") or {}).get("skill"),
        "output": (turn.get("model") or {}).get("output"),
        "action": (turn.get("action") or {}).get("tool"),
        "spoken": turn.get("spoken"),
        "stt_ms": turn.get("stt_ms"),
        "model_ms": (turn.get("model") or {}).get("ms"),
        "bank_ms": (turn.get("bank") or {}).get("ms"),
        "reply_s": latency.get("reply_s"),
        "stages_ms": latency.get("stages_ms"),
    }


# ---------------------------------------------------------------- main


def planned_calls(args: argparse.Namespace) -> tuple[list[list[str]], dict[str, str] | None]:
    """The calls to place, and the voice for each line when they come from a script."""
    if args.script:
        calls = load_script(args.script)
        return [call["lines"] for call in calls], {
            line: call["voice"] for call in calls for line in call["lines"]
        }
    return call_scripts(args.turns), None


async def run(args: argparse.Namespace) -> None:
    scripts, voices = planned_calls(args)
    lines = {line for call in scripts for line in call}
    # Render in a child process: its MLX memory is returned to the system when it exits, so the
    # caller doesn't hold gigabytes the agent needs during the calls.
    render = [sys.executable, "-m", "bench.caller", "--render-only", "--turns", str(args.turns)]
    if args.script:
        render += ["--script", str(args.script)]
    if args.background_db is not None:
        render += ["--background-db", str(args.background_db)]
    subprocess.run(render, check=True)
    audio = render_lines(lines, voices)
    background = None if args.background_db is None else render_background(args.background_db)
    latencies: list[float] = []
    timeouts = overlaps = 0
    config = {
        "url": args.url,
        "turns": args.turns,
        "calls": len(scripts),
        "background_db": args.background_db,
        "concurrency": args.concurrency,
        "script": str(args.script) if args.script else None,
    }
    waiting = list(enumerate(scripts, start=1))

    async def line_worker(line_number: int) -> None:
        nonlocal timeouts, overlaps
        # Lines start a few seconds apart so their turns don't fall in step.
        await asyncio.sleep(line_number * STAGGER_S)
        while waiting:
            number, lines = waiting.pop(0)
            try:
                turns = await place_call(args.url, lines, audio, background)
            except Exception as error:
                print(f"call {number}/{len(scripts)} failed: {type(error).__name__}: {error}")
                continue
            for turn in turns:
                writer.sample(call=number, line=line_number, **turn)
                if turn["overlap"]:
                    overlaps += 1
                elif turn["latency_s"] is None:
                    timeouts += 1
                else:
                    latencies.append(turn["latency_s"])
            done = [t["latency_s"] for t in turns if t["latency_s"] is not None]
            print(
                f"call {number}/{len(scripts)} (line {line_number}): {len(done)}/{len(lines)} "
                f"turns, latencies {[round(v * 1000) for v in done]} ms"
            )
            await asyncio.sleep(1.0)

    with ResultWriter("caller", config) as writer:
        await asyncio.gather(*(line_worker(n) for n in range(args.concurrency)))
        stats = summarize(latencies)
        passed = bool(latencies) and stats["p90"] <= LATENCY_TARGET_P90_S
        writer.summary(
            latency_s=stats,
            timeouts=timeouts,
            overlaps=overlaps,
            target_p90_s=LATENCY_TARGET_P90_S,
            passed=passed,
        )

    print(
        f"\n{stats['n']} turns measured, {timeouts} without a reply, {overlaps} where the agent "
        f"spoke before the caller finished: p50 {ms(stats['p50'])} ms, "
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
    parser.add_argument(
        "--concurrency", type=int, default=1, help="calls in progress at once (default 1)"
    )
    parser.add_argument(
        "--background-db",
        type=float,
        help="Play a noisy room (background talk and noise) this many dB below the caller",
    )
    parser.add_argument(
        "--script",
        type=Path,
        help="place these scripted calls instead of the benchmark's (JSON, see load_script)",
    )
    parser.add_argument("--render-only", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.render_only:
        scripts, voices = planned_calls(args)
        render_lines({line for call in scripts for line in call}, voices)
        if args.background_db is not None:
            render_background(args.background_db)
        return
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
