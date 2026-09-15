"""Start (or reuse) the local mlx-lm server that serves Gemma 4 over an OpenAI-compatible API.

The server runs through ``tellerline.llm_server_main``, which caps MLX's buffer cache.
"""

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from tellerline.config import (
    LLM_CHAT_TEMPLATE_ARGS,
    LLM_PROMPT_CACHE_BYTES,
    LLM_SERVER_HOST,
    LLM_SERVER_PORT,
)

MAX_TOKENS = 200


def base_url(port: int = LLM_SERVER_PORT) -> str:
    return f"http://{LLM_SERVER_HOST}:{port}/v1"


def is_running(port: int = LLM_SERVER_PORT) -> bool:
    try:
        with urllib.request.urlopen(f"{base_url(port)}/models", timeout=2):
            return True
    except (urllib.error.URLError, ConnectionError, TimeoutError):
        return False


def start_server(
    model_id: str, port: int = LLM_SERVER_PORT, log_path: Path | None = None
) -> subprocess.Popen:
    """Launch ``mlx_lm.server`` for ``model_id`` and wait until it answers."""
    command = [
        sys.executable,
        "-m",
        "tellerline.llm_server_main",
        "--model",
        model_id,
        "--host",
        LLM_SERVER_HOST,
        "--port",
        str(port),
        "--temp",
        "0",
        "--max-tokens",
        str(MAX_TOKENS),
        "--chat-template-args",
        json.dumps(LLM_CHAT_TEMPLATE_ARGS),
        "--prompt-cache-bytes",
        str(LLM_PROMPT_CACHE_BYTES),
    ]
    log = log_path.open("w") if log_path else subprocess.DEVNULL
    process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
    deadline = time.monotonic() + 600
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"mlx_lm.server exited early; see {log_path}")
        if is_running(port):
            return process
        time.sleep(1)
    process.terminate()
    raise TimeoutError(f"mlx_lm.server did not start within 10 minutes; see {log_path}")
