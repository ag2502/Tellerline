"""Shared helpers: machine info, percentiles, text boundaries and JSONL result files."""

import json
import platform
import re
import subprocess
import time
from datetime import UTC, datetime
from importlib import metadata
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = ROOT / "results"
DATA_DIR = Path(__file__).resolve().parent / "data"

_PACKAGES = ("pipecat-ai", "mlx", "mlx-lm", "mlx-audio", "kokoro-onnx", "onnxruntime")

# A sentence ends at . ! or ? followed by whitespace; Pipecat hands text to TTS per sentence.
_SENTENCE_END = re.compile(r"[.!?][\"')\]]*\s")
_CLAUSE_END = re.compile(r"[.!?,;:—][\"')\]]*\s")


def _sysctl(key: str) -> str:
    try:
        return subprocess.run(
            ["sysctl", "-n", key], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def power_state() -> dict[str, Any]:
    """Power source, battery level and Low Power Mode: both change how fast the chip runs."""
    try:
        battery = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True).stdout
        settings = subprocess.run(["pmset", "-g"], capture_output=True, text=True).stdout
    except OSError:
        return {}
    level = re.search(r"(\d+)%", battery)
    low_power = re.search(r"lowpowermode\s+(\d)", settings)
    return {
        "on_battery": "Battery Power" in battery,
        "battery_percent": int(level.group(1)) if level else None,
        "low_power_mode": bool(low_power and low_power.group(1) == "1"),
    }


def memory_state() -> dict[str, Any]:
    """How hard macOS is squeezing memory: swap in use and memory held compressed.

    Benchmarks run on a Mac in everyday use; heavy compression or swap slows MLX models, so
    each result records it.
    """
    swap = re.search(r"used = ([\d.]+)M", _sysctl("vm.swapusage"))
    try:
        stats = subprocess.run(["vm_stat"], capture_output=True, text=True).stdout
    except OSError:
        stats = ""
    page = re.search(r"page size of (\d+) bytes", stats)
    compressed = re.search(r"Pages occupied by compressor:\s+(\d+)", stats)
    gib = 1024**3
    return {
        "swap_used_gb": round(float(swap.group(1)) / 1024, 2) if swap else None,
        "compressed_gb": (
            round(int(compressed.group(1)) * int(page.group(1)) / gib, 2)
            if compressed and page
            else None
        ),
    }


def machine_info() -> dict[str, Any]:
    """Describe the hardware and software a result was measured on."""
    memsize = _sysctl("hw.memsize")
    versions = {}
    for package in _PACKAGES:
        try:
            versions[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            versions[package] = None
    return {
        "power": power_state(),
        "memory": memory_state(),
        "chip": _sysctl("machdep.cpu.brand_string"),
        "model": _sysctl("hw.model"),
        "memory_gb": round(int(memsize) / 1024**3) if memsize.isdigit() else None,
        "macos": platform.mac_ver()[0],
        "python": platform.python_version(),
        "packages": versions,
    }


def percentile(values: list[float], q: float) -> float:
    """Linearly interpolated percentile (same definition as numpy's default)."""
    if not values:
        raise ValueError("percentile of empty list")
    if not 0 <= q <= 100:
        raise ValueError("q must be between 0 and 100")
    ordered = sorted(values)
    position = (len(ordered) - 1) * q / 100
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def summarize(values: list[float]) -> dict[str, float | int]:
    """Count, mean and tail percentiles of a list of measurements."""
    if not values:
        return {"n": 0}
    return {
        "n": len(values),
        "mean": sum(values) / len(values),
        "min": min(values),
        "p50": percentile(values, 50),
        "p90": percentile(values, 90),
        "p95": percentile(values, 95),
        "max": max(values),
    }


def has_sentence_end(text: str, final: bool = False) -> bool:
    """True once the text holds a complete sentence that TTS could start speaking."""
    if _SENTENCE_END.search(text):
        return True
    return final and bool(text.strip())


def has_clause_end(text: str, final: bool = False) -> bool:
    """True once the text holds a complete clause (a comma or dash also counts)."""
    if _CLAUSE_END.search(text):
        return True
    return final and bool(text.strip())


class ResultWriter:
    """Append-only JSONL file: one run header, many samples, one summary."""

    def __init__(self, bench: str, config: dict[str, Any]):
        RESULTS_DIR.mkdir(exist_ok=True)
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        self.path = RESULTS_DIR / f"{bench}-{stamp}.jsonl"
        self._file = self.path.open("w")
        self._write(
            {
                "type": "run",
                "bench": bench,
                "started_at": stamp,
                "machine": machine_info(),
                "config": config,
            }
        )

    def _write(self, record: dict[str, Any]) -> None:
        self._file.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._file.flush()

    def sample(self, **fields: Any) -> None:
        self._write({"type": "sample", **fields})

    def summary(self, **fields: Any) -> None:
        self._write({"type": "summary", **fields})

    def close(self) -> None:
        self._file.close()

    def __enter__(self) -> "ResultWriter":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def latest_result(bench: str) -> list[dict[str, Any]] | None:
    """Records of the most recent result file for a benchmark, or None if it never ran."""
    files = sorted(RESULTS_DIR.glob(f"{bench}-*.jsonl"))
    if not files:
        return None
    return [json.loads(line) for line in files[-1].read_text().splitlines() if line.strip()]


def ms(seconds: float) -> float:
    return round(seconds * 1000, 1)


now = time.perf_counter
