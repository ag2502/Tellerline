"""Build and run one call: WebRTC in, Parakeet, turn detection, the agent, Kokoro, WebRTC out."""

import os
import uuid

from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import TTSSpeakFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.turns.user_start import MinWordsUserTurnStartStrategy
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from pipecat.workers.runner import WorkerRunner

from tellerline.agent.observability import TurnLatencyLog
from tellerline.audio.noise import RNNoiseSuppressor
from tellerline.bank.client import BankClient
from tellerline.brain import GREETING, RouterBrain
from tellerline.config import (
    INTERRUPT_MIN_WORDS,
    LLM_MODELS,
    STT_SAMPLE_RATE,
    TTS_DEFAULT_VOICE,
    USER_TURN_STOP_TIMEOUT_S,
    VAD_CONFIDENCE,
    VAD_MIN_VOLUME,
    VAD_START_SECS,
    VAD_STOP_SECS,
)
from tellerline.router.classifier import default_classifier
from tellerline.services.llm import TellerlineLLMService
from tellerline.services.stt import ParakeetMLXSTTService
from tellerline.services.tts import KokoroMLXTTSService
from tellerline.tts.kokoro_mlx import SAMPLE_RATE as TTS_SAMPLE_RATE

LLM_MODEL = LLM_MODELS[os.environ.get("TELLERLINE_LLM", "e2b")]
VOICE = os.environ.get("TELLERLINE_VOICE", TTS_DEFAULT_VOICE)
TRACING = os.environ.get("TELLERLINE_TRACING", "1") == "1"
# Noise handling can be switched off to measure its effect: TELLERLINE_NOISE=0.
NOISE_HANDLING = os.environ.get("TELLERLINE_NOISE", "1") == "1"

transport_params = {
    "webrtc": lambda: TransportParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        audio_in_filter=RNNoiseSuppressor() if NOISE_HANDLING else None,
    ),
}


def user_params() -> LLMUserAggregatorParams:
    """Turn-taking: when the caller has started and finished speaking."""
    if not NOISE_HANDLING:
        return LLMUserAggregatorParams(
            vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=VAD_STOP_SECS)),
            user_turn_stop_timeout=USER_TURN_STOP_TIMEOUT_S,
        )
    vad = VADParams(
        confidence=VAD_CONFIDENCE,
        start_secs=VAD_START_SECS,
        stop_secs=VAD_STOP_SECS,
        min_volume=VAD_MIN_VOLUME,
    )
    return LLMUserAggregatorParams(
        vad_analyzer=SileroVADAnalyzer(params=vad),
        user_turn_strategies=UserTurnStrategies(
            start=[MinWordsUserTurnStartStrategy(min_words=INTERRUPT_MIN_WORDS, use_interim=False)],
        ),
        user_turn_stop_timeout=USER_TURN_STOP_TIMEOUT_S,
    )


async def run_bot(transport: BaseTransport, runner_args: RunnerArguments):
    call_id = f"call-{uuid.uuid4().hex[:8]}"
    logger.info(f"Starting {call_id}")

    bank = BankClient()
    brain = RouterBrain(default_classifier(), today=_today())
    llm = TellerlineLLMService(brain=brain, bank=bank, model=LLM_MODEL)
    stt = ParakeetMLXSTTService()
    tts = KokoroMLXTTSService(voice=VOICE)

    context = LLMContext()
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context, user_params=user_params()
    )
    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            user_aggregator,
            llm,
            tts,
            transport.output(),
            assistant_aggregator,
        ]
    )

    latency_log = TurnLatencyLog(call_id)
    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=STT_SAMPLE_RATE,
            audio_out_sample_rate=TTS_SAMPLE_RATE,
            enable_metrics=True,
        ),
        observers=[latency_log.observer],
        enable_tracing=TRACING,
        conversation_id=call_id,
        idle_timeout_secs=runner_args.pipeline_idle_timeout_secs,
    )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        # The AI disclosure is part of the greeting on every call.
        await worker.queue_frames([TTSSpeakFrame(GREETING)])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info(f"{call_id} ended; turn latencies in {latency_log.path}")
        await runner.cancel()

    runner = WorkerRunner(handle_sigint=runner_args.handle_sigint)
    await runner.add_workers(worker)
    try:
        await runner.run()
    finally:
        await bank.close()


def _today():
    from datetime import date

    return date.today()


async def bot(runner_args: RunnerArguments):
    transport = await create_transport(runner_args, transport_params)
    await run_bot(transport, runner_args)
