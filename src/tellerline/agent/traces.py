"""Print the agent's OpenTelemetry traces as a readable timeline.

    python -m tellerline.agent.traces                 # calls in today's trace file
    python -m tellerline.agent.traces --call call-1a2b3c4d
    python -m tellerline.agent.traces --file results/traces/20260915.jsonl --last 3

Each call is a ``conversation`` span with one ``turn`` span per exchange; inside a turn are the
``stt``, ``llm`` and ``tts`` spans Pipecat records, plus Tellerline's routing attributes.
"""

import argparse
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from tellerline.agent.observability import TRACES_DIR


def _time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _ms(span: dict) -> float:
    return (_time(span["end_time"]) - _time(span["start_time"])).total_seconds() * 1000


def load(path: Path) -> list[dict]:
    with path.open() as file:
        return [json.loads(line) for line in file if line.strip()]


def timeline(spans: list[dict], call: str | None = None, last: int | None = None) -> str:
    by_id = {s["context"]["span_id"]: s for s in spans}
    children = defaultdict(list)
    for span in spans:
        if span.get("parent_id"):
            children[span["parent_id"]].append(span)
    calls = [s for s in spans if s["name"] == "conversation"]
    if call:
        calls = [s for s in calls if s["attributes"].get("conversation.id") == call]
    calls.sort(key=lambda s: s["start_time"])
    if last:
        calls = calls[-last:]

    lines = []
    for conversation in calls:
        attrs = conversation["attributes"]
        started = _time(conversation["start_time"]).astimezone()
        lines.append(
            f"\n{attrs.get('conversation.id')}  started {started:%H:%M:%S}, lasted {_ms(conversation) / 1000:.1f} s"
        )
        turns = sorted(children[conversation["context"]["span_id"]], key=lambda s: s["start_time"])
        for turn in turns:
            t = turn["attributes"]
            latency = t.get("turn.user_bot_latency_seconds")
            head = f"  turn {t.get('turn.number')}"
            if latency is not None:
                head += f"  reply after {latency * 1000:.0f} ms"
            if t.get("turn.was_interrupted"):
                head += "  (interrupted)"
            lines.append(head)
            for span in sorted(children[turn["context"]["span_id"]], key=lambda s: s["start_time"]):
                a = span["attributes"]
                ttfb = a.get("metrics.ttfb")
                ttfb_text = (
                    f"first result {ttfb * 1000:.0f} ms" if isinstance(ttfb, (int, float)) else ""
                )
                if span["name"] == "stt":
                    lines.append(f'    heard   {ttfb_text:<22} "{a.get("transcript", "")}"')
                elif span["name"] == "llm":
                    route = a.get("tellerline.route.step", "?")
                    intent = a.get("tellerline.intent")
                    score = a.get("tellerline.intent.score")
                    routing = f"{route}" + (f" (intent {intent} {score:.2f})" if intent else "")
                    action = a.get("tellerline.action") or "reply"
                    lines.append(
                        f'    decided {ttfb_text:<22} {routing}, {action}: "{a.get("tellerline.spoken", a.get("output", ""))}"'
                    )
                elif span["name"] == "tts":
                    lines.append(f'    spoke   {ttfb_text:<22} "{a.get("text", "")}"')
    missing = [s for s in spans if s.get("parent_id") and s["parent_id"] not in by_id]
    if missing and not lines:
        lines.append("No complete calls found.")
    return "\n".join(lines) if lines else "No calls found."


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "--file", type=Path, default=TRACES_DIR / f"{datetime.now(UTC):%Y%m%d}.jsonl"
    )
    parser.add_argument("--call", help="Only this call id, e.g. call-1a2b3c4d")
    parser.add_argument("--last", type=int, help="Only the last N calls")
    args = parser.parse_args()
    if not args.file.exists():
        raise SystemExit(f"No trace file at {args.file}. Traces are written while the agent runs.")
    print(timeline(load(args.file), args.call, args.last))


if __name__ == "__main__":
    main()
