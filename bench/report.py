"""Turn the latest Phase 0 results into a Markdown report with a projected latency budget.

The projection adds each stage's p90, which overstates the true p90 of the sum: stages are not
all slow on the same turn. It is a conservative go/no-go check, not a measurement; Phase 1
measures real end-to-end turns.

Usage:
    python -m bench.report            # writes results/PHASE0.md
"""

import json
from collections.abc import Callable
from typing import Any

from bench.common import RESULTS_DIR, latest_result
from tellerline.config import LATENCY_TARGET_P90_S, TTS_MLX_VARIANT, VAD_STOP_SECS

# Browser WebRTC send and playback buffering; an estimate until Phase 1 measures it.
TRANSPORT_ESTIMATE_S = 0.08


def _records(path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _summary(records: list[dict] | None) -> list[dict]:
    return [r for r in records or [] if r["type"] == "summary"]


def _latest_where(bench: str, keep: Callable[[dict], bool]) -> list[dict] | None:
    """Most recent result file whose run config passes ``keep``."""
    for path in sorted(RESULTS_DIR.glob(f"{bench}-*.jsonl"), reverse=True):
        records = _records(path)
        if records and keep(records[0].get("config", {})) and _summary(records):
            return records
    return None


def _tts_configs() -> list[dict]:
    """Newest measurement of every Kokoro configuration across all TTS result files."""
    newest: dict[tuple, dict] = {}
    for path in sorted(RESULTS_DIR.glob("tts-*.jsonl")):
        for summary in _summary(_records(path)):
            for config in summary.get("configs", []):
                config = {"engine": "onnx", **config}  # early runs predate the engine field
                key = (config["engine"], config["variant"], config["provider"], config["threads"])
                newest[key] = config
    return list(newest.values())


def _ms(seconds: float | None) -> str:
    return "–" if seconds is None else f"{seconds * 1000:,.0f}"


def _pct(value: float | None) -> str:
    return "–" if value is None else f"{value:.0%}"


def _p90(stats: dict[str, Any] | None) -> float | None:
    return stats.get("p90") if stats and stats.get("n") else None


def build_report() -> str:
    stt, turn, memory, router = (
        latest_result(name) for name in ("stt", "turn", "memory", "router")
    )
    dialogues = _latest_where("dialogues", lambda c: c.get("split") == "test")
    lines = ["# Phase 0 results", ""]
    machine = next(
        (r["machine"] for r in (dialogues or stt or turn or []) if r["type"] == "run"), None
    )
    if machine:
        lines += [
            f"Measured on {machine['model']} ({machine['chip']}, {machine['memory_gb']} GB), "
            f"macOS {machine['macos']}. Packages: "
            + ", ".join(f"{k} {v}" for k, v in machine["packages"].items() if v)
            + ".",
            "",
        ]

    turn_p90 = stt_wide = stt_phone = tts_p90 = None
    turn_cpus = None
    if turn:
        inference = _summary(turn)[0]["inference_s"]
        turn_cpus = min(inference, key=lambda cpus: inference[cpus]["p90"])
        turn_p90 = _p90(inference[turn_cpus])
    if stt:
        stt_latency = _summary(stt)[0]["latency_s"]
        stt_wide, stt_phone = _p90(stt_latency.get("all_wide")), _p90(stt_latency.get("all_phone"))
    tts_configs = _tts_configs()
    chosen = next(
        (c for c in tts_configs if c["engine"] == "mlx" and c["variant"] == TTS_MLX_VARIANT), None
    )
    if chosen:
        tts_p90 = _p90(chosen["first_audio_s"].get("medium"))

    lines += ["## Stage latency", "", "| Stage | p90 (ms) |", "|---|---:|"]
    lines += [
        f"| Silence before turn check (configured) | {_ms(VAD_STOP_SECS)} |",
        f"| Smart Turn v3.2 inference ({turn_cpus} CPU threads) | {_ms(turn_p90)} |",
        f"| Parakeet speech-to-text, browser audio | {_ms(stt_wide)} |",
        f"| Parakeet speech-to-text, phone audio | {_ms(stt_phone)} |",
        f"| Kokoro first audio, medium sentence (MLX {TTS_MLX_VARIANT}) | {_ms(tts_p90)} |",
        f"| Transport and playback (estimate) | {_ms(TRANSPORT_ESTIMATE_S)} |",
        "",
    ]

    if tts_configs:
        lines += [
            "## Kokoro runtimes",
            "",
            "First audio p90 in ms, by sentence length.",
            "",
            "| Runtime | Short | Medium | Long | Real-time factor p50 |",
            "|---|---:|---:|---:|---:|",
        ]
        for c in sorted(tts_configs, key=lambda c: c["first_audio_s"]["medium"]["p90"]):
            name = f"{c['engine']} {c['variant']}"
            if c["engine"] == "onnx":
                name += f" {c['provider']}, threads {c['threads'] or 'default'}"
            stats = c["first_audio_s"]
            lines.append(
                f"| {name} | {_ms(_p90(stats['short']))} | {_ms(_p90(stats['medium']))} | "
                f"{_ms(_p90(stats['long']))} | {c['rtf']['p50']:.3f} |"
            )
        lines.append("")

    router_summary = _summary(router)
    if router_summary:
        r = router_summary[0]
        lines += [
            "## Intent classifier (bge-small-en-v1.5 on CPU)",
            "",
            f"Thresholds chosen on dev: min score {r['thresholds']['min_score']}, "
            f"min margin {r['thresholds']['min_margin']}. Latency p50 "
            f"{_ms(r['latency_s']['p50'])} ms, p90 {_ms(r['latency_s']['p90'])} ms.",
            "",
            "| Split | Top-intent accuracy | Confident turns | Accuracy when confident |",
            "|---|---:|---:|---:|",
        ]
        for split in ("dev", "test"):
            s = r[split]
            lines.append(
                f"| {split} | {_pct(s['accuracy'])} | {_pct(s['confident_rate'])} | "
                f"{_pct(s['confident_accuracy'])} |"
            )
        lines.append("")

    dialogue_summaries = _summary(dialogues)
    if dialogue_summaries:
        lines += [
            "## Agent decisions on the held-out test set",
            "",
            "Single-turn cases plus multi-turn dialogues. Latency is routing plus Gemma 4 time "
            "to the first spoken sentence (reply) or to the complete ACTION line.",
            "",
            "| Model | Brain | Single-turn | Dialogue turns | Dialogues fully right | "
            "Reply p90 (ms) | Action p90 (ms) | Routing p90 (ms) |",
            "|---|---|---:|---:|---:|---:|---:|---:|",
        ]
        for s in dialogue_summaries:
            lat = s["latency_s"]
            lines.append(
                f"| {s['model']} | {s['brain']} | {_pct(s['single_turn_accuracy'])} | "
                f"{_pct(s['dialogue_turn_accuracy'])} | {_pct(s['dialogue_success'])} | "
                f"{_ms(_p90(lat['decision_reply']))} | {_ms(_p90(lat['decision_action']))} | "
                f"{_ms(_p90(lat['route']))} |"
            )
        lines.append("")

        lines += [
            f"## Projected turn latency vs the {LATENCY_TARGET_P90_S} s p90 target",
            "",
            "Silence wait + Smart Turn + Parakeet + agent decision + Kokoro first audio (medium "
            "sentence) + transport, each at p90.",
            "",
            "| Model | Brain | Line | Turn | Projected p90 (ms) | Verdict |",
            "|---|---|---|---|---:|---|",
        ]
        for s in dialogue_summaries:
            for line_name, stt_p90 in (("browser", stt_wide), ("phone", stt_phone)):
                for turn_type, key in (("reply", "decision_reply"), ("action", "decision_action")):
                    parts = [
                        VAD_STOP_SECS,
                        turn_p90,
                        stt_p90,
                        _p90(s["latency_s"][key]),
                        tts_p90,
                        TRANSPORT_ESTIMATE_S,
                    ]
                    if any(part is None for part in parts):
                        continue
                    total = sum(parts)
                    verdict = "within target" if total <= LATENCY_TARGET_P90_S else "over target"
                    lines.append(
                        f"| {s['model']} | {s['brain']} | {line_name} | {turn_type} | "
                        f"{_ms(total)} | {verdict} |"
                    )
        lines.append("")

        for s in dialogue_summaries:
            # Repeats at temperature 0 fail the same turns; list each turn once.
            unique = {(f["conversation"], f["turn"]): f for f in s["failures"]}.values()
            if unique:
                lines += [f"### {s['model']} / {s['brain']}: turns it got wrong", ""]
                for f in unique:
                    lines.append(
                        f"- `{f['conversation']}#{f['turn']}` [{f['step']}] "
                        f'"{f["user"]}" → `{f["text"]}` '
                        f"(expected `{f['expected'].get('tool')}`)"
                    )
                lines.append("")

    memory_summary = _summary(memory)
    if memory_summary:
        lines += ["## Memory (GB)", "", "| Component | Weights | Peak |", "|---|---:|---:|"]
        for name, values in memory_summary[0]["components"].items():
            weights = values.get("weights_gb", values.get("rss_growth_gb"))
            peak = values.get("peak_gb", values.get("rss_peak_gb"))
            lines.append(f"| {name} | {weights:.2f} | {peak:.2f} |")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    path = RESULTS_DIR / "PHASE0.md"
    RESULTS_DIR.mkdir(exist_ok=True)
    path.write_text(build_report())
    print(path.read_text())
    print(f"Written to {path}")


if __name__ == "__main__":
    main()
