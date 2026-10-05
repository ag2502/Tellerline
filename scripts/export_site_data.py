"""Export what the website shows: measured results, the decision log and recorded calls.

Every number on the site comes from a result file under ``results/`` (written by a benchmark on
the MacBook Air M5); every call it replays comes from a recording made by the agent with
``TELLERLINE_RECORD=1``. Nothing is typed in by hand.

    python scripts/export_site_data.py                 # results and decisions only
    python scripts/export_site_data.py --calls         # also the calls in scripts/site_calls.json

Writes ``site/data/site.json``, and for each call ``site/public/calls/<slug>.json`` and
``site/public/calls/<slug>.mp3`` (stereo, the caller panned left of centre and Tellerline right).
"""

import argparse
import json
import re
import wave
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf

from tellerline.brain import GREETING

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
SITE = ROOT / "site"
CALLS_MANIFEST = ROOT / "scripts" / "site_calls.json"
ENVELOPE_HZ = 40  # waveform columns per second of audio


def rows(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def runs(prefix: str) -> list[tuple[Path, list[dict[str, Any]]]]:
    """Result files for one benchmark, oldest first, each with its rows."""
    return [(path, rows(path)) for path in sorted(RESULTS.glob(f"{prefix}-*.jsonl"))]


def header(records: list[dict]) -> dict:
    return next(r for r in records if r.get("type") == "run")


def summary(records: list[dict]) -> dict | None:
    return next((r for r in reversed(records) if r.get("type") == "summary"), None)


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * q / 100
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def spread(values: list[float]) -> dict[str, float]:
    return {
        "n": len(values),
        "p50": round(percentile(values, 50), 3),
        "p90": round(percentile(values, 90), 3),
        "p95": round(percentile(values, 95), 3),
        "max": round(max(values), 3),
    }


# ---------------------------------------------------------------- live calls


def caller_run(records: list[dict]) -> dict[str, Any]:
    """One bench.caller run: latency spread, histogram and the agent's stage times."""
    config = header(records)["config"]
    samples = [r for r in records if r.get("type") == "sample"]
    measured = [s["latency_s"] for s in samples if s.get("latency_s") is not None]
    overlaps = sum(1 for s in samples if s.get("overlap"))
    stages: dict[str, list[float]] = {}
    for sample in samples:
        report = sample.get("agent") or {}
        for key in ("stt_ms", "model_ms", "bank_ms"):
            if report.get(key) is not None:
                stages.setdefault(key, []).append(report[key])
        for key, value in (report.get("stages_ms") or {}).items():
            stages.setdefault(key, []).append(value)
    bins = Counter(int(value * 10) for value in measured)  # 100 ms bins
    histogram = [
        {"from": index / 10, "to": (index + 1) / 10, "count": bins.get(index, 0)}
        for index in range(min(bins), max(bins) + 1)
    ]
    machine = header(records)["machine"]
    return {
        "file": None,
        "calls": len({s.get("call") for s in samples}),
        "turns": len(samples),
        "measured": len(measured),
        "overlaps": overlaps,
        "without_reply": len(samples) - len(measured) - overlaps,
        "concurrency": config.get("concurrency") or 1,
        "background_db": config.get("background_db"),
        "latency_s": spread(measured) if measured else None,
        "histogram": histogram if measured else [],
        "stages_ms": {
            key: {"p50": round(percentile(v, 50), 1), "p90": round(percentile(v, 90), 1)}
            for key, v in sorted(stages.items())
        },
        "machine": {
            "chip": machine.get("chip"),
            "memory_gb": machine.get("memory_gb"),
            "power": machine.get("power"),
            "memory": machine.get("memory"),
        },
        "started_at": header(records)["started_at"],
    }


def live_calls() -> dict[str, Any]:
    complete = [
        (p, r) for p, r in runs("caller") if summary(r) and header(r)["config"].get("turns")
    ]
    gates = [
        (p, r)
        for p, r in complete
        if header(r)["config"]["turns"] >= 200
        and (header(r)["config"].get("concurrency") or 1) == 1
        and header(r)["config"].get("background_db") is None
        and sum(1 for s in r if s.get("type") == "sample") >= 200
    ]
    out: dict[str, Any] = {}
    if gates:
        path, records = gates[-1]
        out["gate"] = {**caller_run(records), "file": path.name}
    capacity = []
    for level in (2, 3, 4, 5, 6):
        found = [
            (p, r)
            for p, r in complete
            if (header(r)["config"].get("concurrency") or 1) == level
            and header(r)["config"].get("background_db") is None
        ]
        if found:
            path, records = found[-1]
            capacity.append({**caller_run(records), "file": path.name})
    if "gate" in out:
        capacity.insert(0, out["gate"])
    out["capacity"] = capacity
    noisy = [(p, r) for p, r in complete if header(r)["config"].get("background_db") is not None]
    if noisy:
        path, records = noisy[-1]
        out["noisy"] = {**caller_run(records), "file": path.name}
    # Calls over the phone line (bench.phone through Asterisk), latest complete run.
    phone = [
        (p, r)
        for p, r in runs("phone")
        if summary(r) and sum(1 for s in r if s.get("type") == "sample") >= 20
    ]
    if phone:
        path, records = phone[-1]
        out["phone"] = {**caller_run(records), "file": path.name}
    # Before this phase's fixes, for the comparison: the first pilot of the session.
    before = RESULTS / "caller-20261005T004952Z.jsonl"
    if before.exists():
        out["before"] = {**caller_run(rows(before)), "file": before.name}
    return out


# ---------------------------------------------------------------- decisions and accuracy


def accuracy() -> dict[str, Any]:
    """The shipped brain (Gemma 4 E2B with the router) on each split, latest run first."""
    latest: dict[str, dict] = {}
    for path, records in runs("dialogues"):
        config = header(records)["config"]
        for item in records:
            if item.get("type") != "summary":
                continue
            if item.get("model") != "e2b" or item.get("brain") != "router":
                continue
            entry = {
                "single_turn": item["single_turn_accuracy"],
                "dialogue_turns": item["dialogue_turn_accuracy"],
                "dialogues": item["dialogue_success"],
                "reply_p90_ms": round(item["latency_s"]["decision_reply"]["p90"] * 1000),
                "action_p90_ms": round(item["latency_s"]["decision_action"]["p90"] * 1000),
                "failures": [f["user"] for f in item.get("failures", [])],
                "file": path.name,
            }
            latest[config["split"]] = entry
    baseline = RESULTS / "dialogues-20261005T003221Z.jsonl"
    if baseline.exists():
        item = summary(rows(baseline))
        latest["holdout_before"] = {
            "single_turn": item["single_turn_accuracy"],
            "dialogue_turns": item["dialogue_turn_accuracy"],
            "dialogues": item["dialogue_success"],
            "file": baseline.name,
        }
    counts = {}
    for split in ("dev", "test", "holdout"):
        cases = (ROOT / "bench" / "data" / f"tool_cases_{split}.jsonl").read_text().splitlines()
        dialogues = (ROOT / "bench" / "data" / f"dialogues_{split}.jsonl").read_text().splitlines()
        counts[split] = {
            "cases": len([c for c in cases if c.strip()]),
            "dialogues": len([d for d in dialogues if d.strip()]),
        }
    latest["counts"] = counts
    return latest


def first_audio() -> dict[str, Any] | None:
    found = runs("first_audio")
    if not found:
        return None
    path, records = found[-1]
    stats = summary(records)["first_audio_ms"]
    return {
        key: {"p50": round(stats[key]["p50"]), "p90": round(stats[key]["p90"])}
        for key in ("sentence", "clause", "clause_cached")
    } | {"file": path.name}


def memory() -> dict[str, Any] | None:
    found = runs("memory")
    if not found:
        return None
    path, records = found[-1]
    components = summary(records)["components"]
    return {
        name: {k: None if v is None else round(v, 2) for k, v in values.items()}
        for name, values in components.items()
    } | {"file": path.name}


def router() -> dict[str, Any] | None:
    found = runs("router")
    if not found:
        return None
    path, records = found[-1]
    item = summary(records)
    return {
        split: {
            "accuracy": round(item[split]["accuracy"], 3),
            "confident_rate": round(item[split]["confident_rate"], 3),
            "confident_accuracy": round(item[split]["confident_accuracy"], 3),
        }
        for split in ("dev", "test")
    } | {"latency_p90_ms": round(item["latency_s"]["p90"] * 1000, 1), "file": path.name}


# Held-out turns that show what the understanding step and its checks changed (D-023).
EXAMPLES = ("h-verify-double-oh", "h-dispute-yesterday", "h-unfreeze-no-digits")
HOLDOUT_BEFORE = "dialogues-20261005T003221Z.jsonl"


def examples() -> list[dict[str, Any]]:
    """The same held-out turns before and after D-023, from the two runs' own records."""
    after_runs = [
        records
        for _, records in runs("dialogues")
        if header(records)["config"]["split"] == "holdout"
        and header(records)["started_at"] > HOLDOUT_BEFORE.split("-")[1].split(".")[0]
    ]
    before_path = RESULTS / HOLDOUT_BEFORE
    if not after_runs or not before_path.exists():
        return []

    def by_case(records: list[dict]) -> dict[str, dict]:
        return {
            r["conversation"]: r
            for r in records
            if r.get("type") == "sample" and r.get("turn") == 0 and r.get("model") == "e2b"
        }

    before, after = by_case(rows(before_path)), by_case(after_runs[-1])
    out = []
    for case in EXAMPLES:
        if case in before and case in after:
            out.append(
                {
                    "case": case,
                    "said": after[case]["user"],
                    "understood": after[case].get("understood") or after[case]["user"],
                    "before": before[case]["text"].strip(),
                    "after": after[case]["text"].strip(),
                    "heard_reply": after[case]["spoken"],
                }
            )
    return out


def template_example() -> dict[str, Any]:
    """What the caller hears for a balance: the bank's numbers through the spoken template."""
    from datetime import date

    from tellerline.banking.responses import respond

    result = {"balance_eur": 1250.40, "available_eur": 1180.40}
    return {
        "action": "ACTION balance account=current",
        "bank": result,
        "spoken": respond("get_balance", {"account": "current"}, result, date.today()),
    }


def film() -> dict[str, Any] | None:
    """The rendered film (scripts/render_film.py), if it has been made."""
    folder = SITE / "public" / "film"
    needed = ("tellerline.mp4", "poster.jpg", "tellerline.vtt")
    if not all((folder / name).exists() for name in needed):
        return None
    return {
        "video": "/film/tellerline.mp4",
        "poster": "/film/poster.jpg",
        "captions": "/film/tellerline.vtt",
        "megabytes": round((folder / "tellerline.mp4").stat().st_size / 1e6, 1),
    }


def customers() -> list[dict[str, Any]]:
    from tellerline.bank.data import KNOWN_CUSTOMERS

    return [
        {"number": number, "name": f"{first} {last}", "born": born, "cards": cards}
        for number, first, last, born, cards in KNOWN_CUSTOMERS
    ]


_DECISION = re.compile(r"^## (D-\d{3}) (.+?) \((\d{4}-\d{2}-\d{2})(?:, (.+?))?\)\s*$", re.M)


def decisions() -> list[dict[str, str]]:
    """docs/DECISIONS.md as entries: id, title, date, and the Decision and Why paragraphs."""
    text = (ROOT / "docs" / "DECISIONS.md").read_text()
    matches = list(_DECISION.finditer(text))
    out = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        body = text[match.end() : end]
        fields = {}
        for label in ("Decision", "Why", "Result", "Considered"):
            found = re.search(rf"\*\*{label}:\*\* (.+?)(?=\n\*\*[A-Z][a-z]+:\*\*|\Z)", body, re.S)
            if found:
                fields[label.lower()] = " ".join(found.group(1).split())
        out.append(
            {
                "id": match.group(1),
                "title": match.group(2),
                "date": match.group(3),
                "note": match.group(4) or "",
                **fields,
            }
        )
    return out


# ---------------------------------------------------------------- calls


def envelope(samples: np.ndarray, rate: int) -> list[int]:
    """Peak level per column, 0-255, ENVELOPE_HZ columns per second."""
    step = rate // ENVELOPE_HZ
    columns = len(samples) // step
    if columns == 0:
        return []
    peaks = np.abs(samples[: columns * step].reshape(columns, step)).max(axis=1)
    scaled = np.clip(np.sqrt(peaks / 32768.0) * 255 * 1.4, 0, 255)  # sqrt: quiet speech shows
    return [int(v) for v in scaled]


def read_track(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path)) as file:
        rate = file.getframerate()
        data = np.frombuffer(file.readframes(file.getnframes()), dtype=np.int16)
    return data, rate


def speaking_intervals(events: list[dict], who: str, duration: float) -> list[list[float]]:
    """[start, end] pairs from the recorded speaking events of the caller or the agent."""
    intervals, start = [], None
    for event in events:
        if event["event"] == f"{who}_started" and start is None:
            start = event["t"]
        elif event["event"] == f"{who}_stopped" and start is not None:
            intervals.append([round(start, 3), round(event["t"], 3)])
            start = None
    if start is not None:
        intervals.append([round(start, 3), round(duration, 3)])
    return intervals


def export_call(slug: str, entry: dict[str, Any]) -> dict[str, Any]:
    folder = RESULTS / "recordings" / entry["recording"]
    call = json.loads((folder / "call.json").read_text())
    caller, rate = read_track(folder / "caller.wav")
    agent, _ = read_track(folder / "agent.wav")
    duration = len(agent) / rate

    # A gentle pan rather than hard left and right, which is tiring on headphones.
    left = 0.8 * caller.astype(np.float32) + 0.35 * agent.astype(np.float32)
    right = 0.35 * caller.astype(np.float32) + 0.8 * agent.astype(np.float32)
    stereo = np.clip(np.stack([left, right], axis=1), -32768, 32767).astype(np.int16)
    out = SITE / "public" / "calls"
    out.mkdir(parents=True, exist_ok=True)
    # 80 kbps constant: plenty for speech at 24 kHz, half the size of the default.
    sf.write(
        out / f"{slug}.mp3",
        stereo,
        rate,
        format="MP3",
        compression_level=0.5,
        bitrate_mode="CONSTANT",
    )

    turns = []
    for turn in call["turns"]:
        turns.append(
            {
                key: turn.get(key)
                for key in (
                    "turn",
                    "t",
                    "heard",
                    "understood",
                    "stt_ms",
                    "route",
                    "model",
                    "action",
                    "instead",
                    "bank",
                    "spoken",
                    "reply_s",
                    "stages_ms",
                )
            }
        )
    record = {
        "slug": slug,
        "title": entry["title"],
        "summary": entry["summary"],
        "call_id": call["call_id"],
        "greeting": GREETING,
        "recorded_at": datetime.fromtimestamp(call["started_at"], UTC).isoformat(),
        "llm": call.get("llm"),
        "voice": call.get("voice"),
        "duration_s": round(duration, 2),
        "caller_speaking": speaking_intervals(call["events"], "caller", duration),
        "agent_speaking": speaking_intervals(call["events"], "agent", duration),
        "turns": turns,
        "envelope_hz": ENVELOPE_HZ,
        "envelope": {"caller": envelope(caller, rate), "agent": envelope(agent, rate)},
        "audio": f"/calls/{slug}.mp3",
    }
    target = out / f"{slug}.json"
    target.write_text(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
    print(f"call {slug}: {duration:.1f} s, {len(turns)} turns -> {target.relative_to(ROOT)}")
    return {k: record[k] for k in ("slug", "title", "summary", "duration_s")}


# ---------------------------------------------------------------- main


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calls", action="store_true", help="also export the recorded calls")
    args = parser.parse_args()

    data = {
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "live": live_calls(),
        "accuracy": accuracy(),
        "first_audio": first_audio(),
        "memory": memory(),
        "router": router(),
        "decisions": decisions(),
        "examples": examples(),
        "template": template_example(),
        "customers": customers(),
        "film": film(),
    }
    if args.calls:
        manifest = json.loads(CALLS_MANIFEST.read_text())
        data["calls"] = [export_call(slug, entry) for slug, entry in manifest.items()]
    else:
        existing = SITE / "data" / "site.json"
        if existing.exists():
            data["calls"] = json.loads(existing.read_text()).get("calls", [])
    (SITE / "data").mkdir(parents=True, exist_ok=True)
    (SITE / "data" / "site.json").write_text(json.dumps(data, indent=1, ensure_ascii=False))
    gate = data["live"].get("gate")
    if gate:
        print(f"gate: {gate['measured']} turns, p90 {gate['latency_s']['p90']} s ({gate['file']})")
    print(f"decisions: {len(data['decisions'])}, wrote site/data/site.json")


if __name__ == "__main__":
    main()
