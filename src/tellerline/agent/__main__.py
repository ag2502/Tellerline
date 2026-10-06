"""Start everything a call needs, then serve the browser call page and the phone line.

    python -m tellerline.agent            # open http://localhost:7860/call/

Starts the mock bank (in this process) and the Gemma 4 server (a child process) unless they're
already running, preloads the speech models and intent classifier so the first call doesn't
wait for them, then hands over to Pipecat's development runner with the WebRTC transport.
Asterisk hands phone calls to the same server at /phone (tellerline.agent.phone, docs/PHONE.md).
"""

import asyncio
import atexit
import sys
import threading
import time
import urllib.error
import urllib.request

import uvicorn
from loguru import logger

from tellerline.agent.bot import (  # noqa: F401  (the runner looks up `bot`)
    LLM_MODEL,
    TRACING,
    VOICE,
    bot,
)
from tellerline.agent.observability import RESULTS_DIR, setup_file_tracing
from tellerline.agent.phone import PATH as PHONE_PATH
from tellerline.agent.phone import mount_phone_line
from tellerline.bank.api import create_app
from tellerline.bank.client import BANK_URL
from tellerline.config import KOKORO_MLX_MODELS, STT_MODEL, TTS_MLX_VARIANT
from tellerline.llm_server import is_running, start_server
from tellerline.router.classifier import default_classifier
from tellerline.services.mlx_thread import limit_mlx_cache, run_mlx
from tellerline.services.stt import load_parakeet
from tellerline.services.stt import warm_up as warm_up_stt
from tellerline.services.tts import load_kokoro, warm_phrases
from tellerline.services.tts import warm_up as warm_up_tts


def _reachable(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=1):
            return True
    except (urllib.error.URLError, ConnectionError, TimeoutError):
        return False


def start_bank() -> None:
    if _reachable(f"{BANK_URL}/health"):
        logger.info("Using the mock bank already running")
        return
    server = uvicorn.Server(
        uvicorn.Config(create_app(), host="127.0.0.1", port=8090, log_level="warning")
    )
    threading.Thread(target=server.run, daemon=True, name="bank").start()
    while not _reachable(f"{BANK_URL}/health"):
        time.sleep(0.1)
    logger.info(f"Mock bank running at {BANK_URL}")


def start_llm() -> None:
    if is_running():
        logger.info("Using the mlx-lm server already running")
        return
    logs = RESULTS_DIR / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    logger.info(f"Starting mlx-lm server for {LLM_MODEL} (first start can take a minute)")
    process = start_server(LLM_MODEL, log_path=logs / "mlx-server-agent.log")
    atexit.register(process.terminate)


async def preload() -> None:
    """Load and warm every model once, so no call waits for loading or kernel compilation."""
    await run_mlx(limit_mlx_cache)
    parakeet = await run_mlx(load_parakeet, STT_MODEL)
    await run_mlx(warm_up_stt, parakeet)
    kokoro = await run_mlx(load_kokoro, KOKORO_MLX_MODELS[TTS_MLX_VARIANT])
    await run_mlx(warm_up_tts, kokoro, VOICE)
    rendered = await run_mlx(warm_phrases, kokoro, fixed_phrases(), VOICE)
    logger.info(f"Pre-rendered {rendered} fixed phrases in the {VOICE} voice")
    default_classifier().predict("warm up")
    await warm_llm_prompts()
    logger.info("Models, intent classifier and LLM prompt cache warmed up")


def fixed_phrases() -> list[str]:
    """Everything the agent says word for word on many calls, so its audio is ready in advance."""
    from tellerline.actions import common_questions
    from tellerline.banking.responses import FIXED_PHRASES
    from tellerline.brain import ANYTHING_ELSE, DIDNT_CATCH, GREETING, HELLO_AGAIN, VERIFY_FIRST
    from tellerline.services.llm import CANT_DO_NOW, NOT_VERIFIED_TRANSFER

    return [
        GREETING,
        VERIFY_FIRST,
        ANYTHING_ELSE,
        *FIXED_PHRASES,
        *common_questions(),
        DIDNT_CATCH,
        HELLO_AGAIN,
        CANT_DO_NOW,
        NOT_VERIFIED_TRANSFER,
    ]


async def warm_llm_prompts() -> None:
    """Send every step's system prompt once so the server has each prefix cached."""
    from datetime import date

    from openai import AsyncOpenAI

    from tellerline.brain import opening_history
    from tellerline.llm_server import base_url
    from tellerline.prompts import build_system_prompt
    from tellerline.router.skills import SKILL_ACTIONS, build_skill_prompt

    today = date.today()
    prompts = [build_system_prompt(today, "assist", "actions")]
    for skill in SKILL_ACTIONS:
        prompts.append(build_skill_prompt(skill, today, verified=skill != "identity"))
    client = AsyncOpenAI(base_url=base_url(), api_key="not-needed")
    for system in prompts:
        messages = [{"role": "system", "content": system}, *opening_history()]
        messages.append({"role": "user", "content": "Hello."})
        await client.chat.completions.create(model=LLM_MODEL, messages=messages, max_tokens=1)
    await client.close()


def main() -> None:
    start_bank()
    start_llm()
    asyncio.run(preload())
    if TRACING:
        logger.info(f"Tracing to {setup_file_tracing()}")
    if not {"-t", "--transport"} & set(sys.argv):
        sys.argv += ["-t", "webrtc"]
    from pipecat.runner.run import app
    from pipecat.runner.run import main as run_runner

    mount_call_page(app)
    mount_phone_line(app)
    logger.info("Call page: http://localhost:7860/call/")
    logger.info(f"Phone line for Asterisk: ws://localhost:7860{PHONE_PATH} (docs/PHONE.md)")
    run_runner()


def mount_call_page(app) -> None:
    """Serve Tellerline's own call page at /call and send the site root there.

    Pipecat's Playground (still at /client) is built for any bot, including video panels a
    voice-only bank line doesn't have. Routes added here take precedence over the runner's.
    """
    from pathlib import Path

    from fastapi.responses import RedirectResponse
    from fastapi.staticfiles import StaticFiles

    static = Path(__file__).parent / "static"
    app.mount("/call", StaticFiles(directory=static, html=True), name="tellerline-call")

    @app.get("/", include_in_schema=False)
    async def root():
        return RedirectResponse(url="/call/")


if __name__ == "__main__":
    main()
