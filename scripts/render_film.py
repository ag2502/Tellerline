"""Render the website's film from a recorded call: the replay drawn frame by frame, with the
call's own audio underneath.

Needs the site running with the call exported (scripts/export_site_data.py --calls) and the film
extra installed (``uv pip install -e ".[film]"`` then ``playwright install chromium``):

    cd site && npm run build && npm run start      # serves /render-film/<slug> on port 3000
    python scripts/render_film.py stolen-card

Writes site/public/film/tellerline.mp4 (H.264 and AAC), poster.jpg and tellerline.vtt.
"""

import argparse
import json
import math
import re
import subprocess
import tempfile
import time
from pathlib import Path

import imageio_ffmpeg
import numpy as np
import soundfile as sf
from export_site_data import read_track, stereo_mix  # alongside this script in scripts/
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
FILM = SITE / "public" / "film"
FPS = 30
INTRO_S = 6  # must match INTRO_S and OUTRO_S in site/components/FilmFrame.tsx
OUTRO_S = 6


def soundtrack(slug: str, out: Path) -> None:
    """The call's two recorded voices, mixed as the site mixes them, with the film's pre-roll."""
    manifest = json.loads((ROOT / "scripts" / "site_calls.json").read_text())
    folder = ROOT / "results" / "recordings" / manifest[slug]["recording"]
    caller, rate = read_track(folder / "caller.wav")
    agent, _ = read_track(folder / "agent.wav")
    stereo = stereo_mix(caller, agent)

    def silence(seconds: float) -> np.ndarray:
        return np.zeros((int(rate * seconds), 2), dtype=np.float32)

    audio = np.concatenate([silence(INTRO_S), stereo, silence(OUTRO_S)])
    sf.write(out, audio, rate, subtype="PCM_16")


def frames(url: str, slug: str, folder: Path) -> tuple[int, float]:
    """Screenshot every frame; returns the frame count and the time of the first action."""
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        page = browser.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
        page.goto(f"{url}/render-film/{slug}", wait_until="networkidle")
        page.wait_for_selector("html[data-film-ready]")
        page.evaluate("document.fonts.ready")
        length = page.evaluate("window.__filmLength")
        count = math.ceil(length * FPS)
        started = time.perf_counter()
        for index in range(count):
            page.evaluate("t => window.__setFilmTime(t)", index / FPS)
            page.screenshot(path=str(folder / f"{index:05d}.png"))
            if index % 300 == 0:
                print(f"frame {index}/{count} ({time.perf_counter() - started:.0f} s)")
        browser.close()
    return count, length


def encode(folder: Path, audio: Path, out: Path) -> None:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-loglevel",
            "error",
            "-framerate",
            str(FPS),
            "-i",
            str(folder / "%05d.png"),
            "-i",
            str(audio),
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "20",
            "-tune",
            "stillimage",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "128k",
            "-movflags",
            "+faststart",
            "-shortest",
            str(out),
        ],
        check=True,
    )


def poster(folder: Path, call: dict, out: Path) -> None:
    """The frame just after the first ACTION line, when the screen says the most."""
    actions = [t["t"] for t in call["turns"] if t["model"]["output"].startswith("ACTION")]
    moment = INTRO_S + (actions[1] if len(actions) > 1 else actions[0] if actions else 10) + 1.5
    index = min(int(moment * FPS), len(list(folder.glob("*.png"))) - 1)
    subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-y",
            "-loglevel",
            "error",
            "-i",
            str(folder / f"{index:05d}.png"),
            "-q:v",
            "3",
            str(out),
        ],
        check=True,
    )


def stamp(seconds: float) -> str:
    minutes, rest = divmod(max(0.0, seconds), 60)
    hours, minutes = divmod(int(minutes), 60)
    return f"{hours:02d}:{minutes:02d}:{rest:06.3f}"


def captions(call: dict, out: Path) -> None:
    """WebVTT from the call: who spoke, when, and what was said.

    Turns are paired with the audio the way the site's replay pairs them (site/lib/timeline.ts):
    a turn's caller speech is what they started saying since the last reply and before the agent
    answered, and its reply is what the agent said from then until the caller spoke again, which
    can start just before the turn's report.
    """
    epsilon = 0.05
    agent = sorted(call["agent_speaking"])
    caller = sorted(call["caller_speaking"])
    turns = sorted(call["turns"], key=lambda t: t["t"])
    cues = []
    first_caller = caller[0][0] if caller else call["duration_s"]
    greeting = [span for span in agent if span[0] < first_caller]
    if greeting:
        cues.append((greeting[0][0], greeting[-1][1], f"Tellerline: {call['greeting']}"))
    boundary = greeting[-1][1] if greeting else 0.0
    for turn in turns:
        # What the caller started saying since the last reply and before the agent answered;
        # it can run past the answer when they talk over the reply.
        said = [s for s in caller if s[0] >= boundary - epsilon and s[0] <= turn["t"] + epsilon]
        if not said:
            said = [s for s in caller if s[0] <= turn["t"] + epsilon][-1:]
        if not said:
            continue
        caller_start, caller_end = said[0][0], said[-1][1]
        # What the caller said, from the call's script where there is one, not the transcript.
        cues.append((caller_start, caller_end, f"Caller: {turn.get('said') or turn['heard']}"))
        next_caller = next((s[0] for s in caller if s[0] > said[-1][0] + epsilon), float("inf"))
        reply = [
            s
            for s in agent
            if s[0] >= max(caller_start, turn["t"] - 0.5 - epsilon) and s[0] < next_caller
        ]
        if reply:
            cues.append((reply[0][0], reply[-1][1], f"Tellerline: {turn['spoken']}"))
            boundary = max(caller_end, reply[-1][1])
        else:
            boundary = caller_end
    lines = ["WEBVTT", ""]
    for start, end, text in (piece for cue in cues for piece in sentences(*cue)):
        lines += [f"{stamp(start + INTRO_S)} --> {stamp(end + INTRO_S)}", text, ""]
    out.write_text("\n".join(lines))


LONGEST_CUE_S = 6.0
CAPTION_CHARS = 84  # two lines of 42, the usual caption limit


def caption_chunks(sentence: str) -> list[str]:
    """A sentence in pieces of at most CAPTION_CHARS, broken between words, after a comma when
    there's one in the second half of a piece."""
    pieces: list[str] = []
    current: list[str] = []
    for word in sentence.split():
        if current and len(" ".join([*current, word])) > CAPTION_CHARS:
            text = " ".join(current)
            cut = text.rfind(", ")
            if cut > CAPTION_CHARS // 2:
                pieces.append(text[: cut + 1])
                current = text[cut + 2 :].split()
            else:
                pieces.append(text)
                current = []
        current.append(word)
    if current:
        pieces.append(" ".join(current))
    # A last scrap ("1996.") reads better at the end of the piece before.
    if len(pieces) > 1 and len(pieces[-1]) < 24:
        pieces[-2:] = [f"{pieces[-2]} {pieces[-1]}"]
    return pieces


def sentences(start: float, end: float, text: str) -> list[tuple[float, float, str]]:
    """A long cue as one cue per sentence (or caption-length piece of one), each timed by its
    share of the characters."""
    speaker, _, words = text.partition(": ")
    parts = [
        piece
        for sentence in re.split(r"(?<=[.?!])\s+", words)
        for piece in caption_chunks(sentence)
    ]
    if end - start <= LONGEST_CUE_S or len(parts) < 2:
        return [(start, end, text)]
    total = sum(len(part) for part in parts)
    pieces, at = [], start
    for part in parts:
        length = (end - start) * len(part) / total
        pieces.append((at, at + length, f"{speaker}: {part}"))
        at += length
    return pieces


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("slug", help="an exported call, e.g. stolen-card")
    parser.add_argument("--url", default="http://localhost:3000")
    args = parser.parse_args()

    call = json.loads((SITE / "public" / "calls" / f"{args.slug}.json").read_text())
    FILM.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        work = Path(temporary)
        (work / "frames").mkdir()
        soundtrack(args.slug, work / "audio.wav")
        count, length = frames(args.url, args.slug, work / "frames")
        print(f"{count} frames for {length:.1f} s; encoding")
        encode(work / "frames", work / "audio.wav", FILM / "tellerline.mp4")
        poster(work / "frames", call, FILM / "poster.jpg")
    captions(call, FILM / "tellerline.vtt")
    size = (FILM / "tellerline.mp4").stat().st_size / 1e6
    print(f"site/public/film/tellerline.mp4: {size:.1f} MB, poster.jpg and tellerline.vtt written")


if __name__ == "__main__":
    main()
