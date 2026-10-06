"""Build and run one call: audio in, Parakeet, turn detection, the agent, Kokoro, audio out.

Calls arrive over WebRTC from the browser call page (Pipecat's development runner) or from
Asterisk as phone calls (tellerline.agent.phone); both run the same pipeline.
"""

import os
import uuid

from loguru import logger
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import TTSSpeakFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.processors.frameworks.rtvi.frames import RTVIServerMessageFrame
from pipecat.runner.types import RunnerArguments
from pipecat.runner.utils import create_transport
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.turns.user_turn_strategies import UserTurnStrategies
from pipecat.workers.runner import WorkerRunner

from tellerline.agent import warm
from tellerline.agent.observability import TurnLatencyLog
from tellerline.agent.recorder import CallRecorder, CallTimeline, TimelineObserver
from tellerline.agent.turns import turn_start_strategies, turn_stop_strategies
from tellerline.audio.noise import RNNoiseSuppressor
from tellerline.audio.vad import CallerVAD
from tellerline.bank.client import BankClient
from tellerline.brain import GREETING, RouterBrain
from tellerline.config import (
    LLM_MODELS,
    PHONE_VAD_CONFIDENCE,
    STT_SAMPLE_RATE,
    TTS_DEFAULT_VOICE,
    USER_TURN_STOP_TIMEOUT_S,
    VAD_CONFIDENCE,
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
# Save each call's timeline and both voices under results/recordings/ (off by default: a real
# person's voice shouldn't be kept unless they choose to).
RECORDING = os.environ.get("TELLERLINE_RECORD", "0") == "1"

transport_params = {
    "webrtc": lambda: TransportParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        audio_in_filter=RNNoiseSuppressor() if NOISE_HANDLING else None,
    ),
}


def user_params(llm: TellerlineLLMService, line: str = "webrtc") -> LLMUserAggregatorParams:
    """Turn-taking: when the caller has started and finished speaking.

    With noise handling off (to measure its effect) these are Pipecat's defaults. A phone line
    takes a lower VAD confidence: Silero is less sure of telephone-band speech.
    """
    if not NOISE_HANDLING:
        return LLMUserAggregatorParams(
            vad_analyzer=CallerVAD(params=VADParams(stop_secs=VAD_STOP_SECS), caller_gate=False),
            user_turn_stop_timeout=USER_TURN_STOP_TIMEOUT_S,
        )
    vad = VADParams(
        confidence=PHONE_VAD_CONFIDENCE if line == "phone" else VAD_CONFIDENCE,
        start_secs=VAD_START_SECS,
        stop_secs=VAD_STOP_SECS,
    )
    return LLMUserAggregatorParams(
        # Gated on the caller's own speech level, in place of Pipecat's volume threshold.
        vad_analyzer=CallerVAD(params=vad),
        user_turn_strategies=UserTurnStrategies(
            start=turn_start_strategies(lambda: llm.ending), stop=turn_stop_strategies()
        ),
        user_turn_stop_timeout=USER_TURN_STOP_TIMEOUT_S,
    )


async def run_bot(transport: BaseTransport, runner_args: RunnerArguments, line: str = "webrtc"):
    """Run one call. `line` names how the caller is connected ("webrtc" or "phone")."""
    call_id = f"call-{uuid.uuid4().hex[:8]}"
    logger.info(f"Starting {call_id} ({line})")

    timeline = CallTimeline(
        call_id,
        metadata={
            "llm": LLM_MODEL,
            "voice": VOICE,
            "noise_handling": NOISE_HANDLING,
            "line": line,
        },
    )
    recorder = CallRecorder(timeline) if RECORDING else None
    bank = BankClient()
    brain = RouterBrain(default_classifier(), today=_today())
    stt = ParakeetMLXSTTService(timeline=timeline)
    llm = TellerlineLLMService(
        brain=brain,
        bank=bank,
        model=LLM_MODEL,
        timeline=timeline,
        whole_turn=stt.turn_transcript,
    )
    tts = KokoroMLXTTSService(voice=VOICE)

    context = LLMContext()
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context, user_params=user_params(llm, line)
    )
    processors = [
        transport.input(),
        stt,
        user_aggregator,
        llm,
        tts,
        transport.output(),
        assistant_aggregator,
    ]
    if recorder is not None:
        processors.append(recorder.processor)
    pipeline = Pipeline(processors)

    async def on_latency(seconds: float, breakdown: dict | None) -> None:
        record = timeline.add_latency(seconds, breakdown)
        if record is not None:
            message = {
                "type": "tellerline-latency",
                "turn": record["turn"],
                "reply_s": record["reply_s"],
                "stages_ms": record["stages_ms"],
            }
            await worker.queue_frames([RTVIServerMessageFrame(data=message)])

    latency_log = TurnLatencyLog(call_id, on_latency=on_latency)
    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=STT_SAMPLE_RATE,
            audio_out_sample_rate=TTS_SAMPLE_RATE,
            enable_metrics=True,
        ),
        observers=[latency_log.observer, TimelineObserver(timeline)],
        enable_tracing=TRACING,
        conversation_id=call_id,
        idle_timeout_secs=runner_args.pipeline_idle_timeout_secs,
    )

    connected = False

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        nonlocal connected
        # The AI disclosure is part of the greeting on every call.
        await worker.queue_frames([TTSSpeakFrame(GREETING)])
        connected = True
        warm.call_started(lambda: warm.rewarm_models(LLM_MODEL, VOICE))

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info(f"{call_id} ended; turn latencies in {latency_log.path}")
        await runner.cancel()

    runner = WorkerRunner(handle_sigint=runner_args.handle_sigint)
    await runner.add_workers(worker)
    try:
        await runner.run()
    finally:
        if connected:
            warm.call_ended()
        await bank.close()
        if recorder is not None and (saved := await recorder.save()):
            logger.info(f"{call_id} recorded to {saved}")


def _today():
    from datetime import date

    return date.today()


async def bot(runner_args: RunnerArguments):
    transport = await create_transport(runner_args, transport_params)
    await run_bot(transport, runner_args)
