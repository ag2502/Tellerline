"""Per-turn latency logs and OpenTelemetry traces, written as JSON lines under ``results/``.

Latency comes from Pipecat's ``UserBotLatencyObserver``: the time from the caller's voice
activity stopping to the bot's first audio frame, with a breakdown by stage. Traces use
Pipecat's OpenTelemetry instrumentation and a small file exporter, so nothing needs a
collector running.
"""

import json
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from pipecat.observers.user_bot_latency_observer import UserBotLatencyObserver

RESULTS_DIR = Path(__file__).resolve().parents[3] / "results"
CALLS_DIR = RESULTS_DIR / "calls"
TRACES_DIR = RESULTS_DIR / "traces"


class TurnLatencyLog:
    """Writes one JSON line per measured turn for a call."""

    def __init__(
        self,
        call_id: str,
        directory: Path = CALLS_DIR,
        on_latency: Callable[[float, dict | None], Awaitable[None]] | None = None,
    ):
        directory.mkdir(parents=True, exist_ok=True)
        self.path = directory / f"{call_id}.jsonl"
        self.call_id = call_id
        self.observer = UserBotLatencyObserver()
        self._pending_breakdown: dict | None = None
        self._on_latency = on_latency

        @self.observer.event_handler("on_latency_breakdown")
        async def on_breakdown(_, breakdown):
            self._pending_breakdown = breakdown.model_dump(mode="json")

        @self.observer.event_handler("on_latency_measured")
        async def on_measured(_, latency_seconds: float):
            self._write(
                {
                    "call_id": call_id,
                    "at": datetime.now(UTC).isoformat(),
                    "latency_s": latency_seconds,
                    "breakdown": self._pending_breakdown,
                }
            )
            logger.info(f"Turn latency {latency_seconds * 1000:.0f} ms")
            if self._on_latency is not None:
                await self._on_latency(latency_seconds, self._pending_breakdown)
            self._pending_breakdown = None

    def _write(self, record: dict) -> None:
        with self.path.open("a") as file:
            file.write(json.dumps(record) + "\n")


class JsonlSpanExporter(SpanExporter):
    """Appends finished spans to a JSON-lines file."""

    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._file = path.open("a")

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        for span in spans:
            self._file.write(span.to_json(indent=None) + "\n")
        self._file.flush()
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        self._file.close()


def setup_file_tracing(service_name: str = "tellerline") -> Path:
    """Enable Pipecat's OpenTelemetry spans, exported to ``results/traces/<date>.jsonl``."""
    from pipecat.utils.tracing.setup import setup_tracing

    path = TRACES_DIR / f"{datetime.now(UTC):%Y%m%d}.jsonl"
    setup_tracing(service_name=service_name, exporter=JsonlSpanExporter(path))
    return path
