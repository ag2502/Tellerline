"""Phone calls through Asterisk: the same agent, answering a SIP call.

Asterisk answers the call (from a softphone, or from a phone number on a SIP trunk) and hands it
to the agent with its WebSocket channel driver, chan_websocket: for each call it opens a websocket
to /phone on the agent's server and streams the caller's audio as 16 kHz signed linear PCM
(slin16) in binary messages, with control events such as MEDIA_START as JSON text. The agent's
audio goes back the same way. telephony/asterisk has the configuration and docs/PHONE.md the
setup.

The call runs the browser call's pipeline (tellerline.agent.bot.run_bot). What differs belongs to
the line, not the agent:

- The call counts as connected when Asterisk starts the media, so the greeting is never sent
  before Asterisk has said what audio format the call uses.
- Audio goes out at the pace it plays, at most LEAD_S ahead. Asterisk queues whatever it's sent,
  and seconds of queued speech would leave the agent believing it had stopped talking while the
  caller still hears it, which would break barge-in and cut off the goodbye at the end of a call.
- An interruption flushes Asterisk's queue (FLUSH_MEDIA), and the end of a call hangs up (HANGUP).
"""

import asyncio
import json
import time
from collections.abc import Awaitable, Callable

from fastapi import WebSocket
from loguru import logger
from pipecat.audio.dtmf.types import KeypadEntry
from pipecat.audio.filters.base_audio_filter import BaseAudioFilter
from pipecat.audio.utils import create_stream_resampler
from pipecat.frames.frames import (
    CancelFrame,
    EndFrame,
    Frame,
    InputAudioRawFrame,
    InputDTMFFrame,
    InputTransportMessageFrame,
    InterruptionFrame,
    OutputAudioRawFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessorSetup
from pipecat.runner.types import WebSocketRunnerArguments
from pipecat.serializers.base_serializer import FrameSerializer
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketOutputTransport,
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)

# The format telephony/asterisk/extensions.conf dials the agent with: 16 kHz signed linear.
CHANNEL_FORMAT = "slin16"
CHANNEL_RATE = 16_000
PACKET_BYTES = 640  # 20 ms of slin16: Asterisk's optimal frame size for the format
LEAD_S = 0.2  # how far ahead of playback the agent's audio may run
PATH = "/phone"


def parse_event(text: str) -> dict:
    """A chan_websocket control event, in either of its formats: JSON, or the older plain text
    ("MEDIA_START connection_id:... format:slin16 ...")."""
    text = text.strip()
    if text.startswith("{"):
        try:
            event = json.loads(text)
        except ValueError:
            return {}
        return event if isinstance(event, dict) else {}
    name, *fields = text.split() or [""]
    event = {"event": name}
    for field in fields:
        key, _, value = field.partition(":")
        event[key] = value
    return event


class AsteriskSerializer(FrameSerializer):
    """Pipecat frames to and from Asterisk's WebSocket channel."""

    def __init__(self) -> None:
        super().__init__()
        self._pipeline_rate = 0
        self._json = True
        self._input_resampler = create_stream_resampler()
        self._output_resampler = create_stream_resampler()
        self.on_media_start: Callable[[dict], Awaitable[None]] | None = None

    async def setup(self, setup: FrameProcessorSetup) -> None:
        self._pipeline_rate = setup.audio_in_sample_rate

    async def serialize(self, frame: Frame) -> str | bytes | None:
        if isinstance(frame, OutputAudioRawFrame):
            audio = await self._output_resampler.resample(
                frame.audio, frame.sample_rate, CHANNEL_RATE
            )
            return audio or None
        if isinstance(frame, InterruptionFrame):
            return self._command("FLUSH_MEDIA")
        if isinstance(frame, (EndFrame, CancelFrame)):
            return self._command("HANGUP")
        return None

    async def deserialize(self, data: str | bytes) -> Frame | None:
        if isinstance(data, bytes):
            audio = await self._input_resampler.resample(data, CHANNEL_RATE, self._pipeline_rate)
            if not audio:
                return None
            return InputAudioRawFrame(audio=audio, num_channels=1, sample_rate=self._pipeline_rate)
        event = parse_event(data)
        name = event.get("event")
        if name == "MEDIA_START":
            # Answer in the format Asterisk speaks.
            self._json = data.lstrip().startswith("{")
            if event.get("format") != CHANNEL_FORMAT:
                logger.error(
                    f"Asterisk sent {event.get('format')} audio; the agent expects {CHANNEL_FORMAT}"
                    " (Dial(WebSocket/.../c(slin16)) in extensions.conf)"
                )
            if self.on_media_start is not None:
                await self.on_media_start(event)
            return InputTransportMessageFrame(message=event)
        if name == "DTMF_END":
            try:
                return InputDTMFFrame(KeypadEntry(str(event.get("digit", ""))))
            except ValueError:
                return None
        logger.debug(f"Asterisk: {data}")
        return None

    def _command(self, name: str) -> str:
        return json.dumps({"command": name}) if self._json else name


class Pacer:
    """Keeps the audio sent ahead of what the caller has heard to at most `lead_s`."""

    def __init__(self, lead_s: float = LEAD_S) -> None:
        self.lead_s = lead_s
        self._played_until = 0.0  # when the audio sent so far will have finished playing

    def delay(self, now: float, chunk_s: float) -> float:
        """Seconds to wait after sending a chunk of `chunk_s` seconds at time `now`."""
        self._played_until = max(self._played_until, now) + chunk_s
        return max(0.0, self._played_until - now - self.lead_s)

    def reset(self) -> None:
        self._played_until = 0.0


class PacedOutput(FastAPIWebsocketOutputTransport):
    """Pipecat's websocket output, sending at the pace the caller hears it (see Pacer).

    Pipecat's own pacing keeps a single chunk (40 ms) ahead, so any busier moment than that
    leaves a gap in what the caller hears; this keeps LEAD_S ahead instead.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._pacer = Pacer()

    async def _write_audio_sleep(self) -> None:
        chunk_s = self.audio_chunk_size / (2 * self._params.audio_out_channels * self.sample_rate)
        wait = self._pacer.delay(time.monotonic(), chunk_s)
        if wait > 0:
            await asyncio.sleep(wait)

    async def process_frame(self, frame: Frame, direction: FrameDirection) -> None:
        await super().process_frame(frame, direction)
        if isinstance(frame, InterruptionFrame):
            self._pacer.reset()


class PhoneTransport(FastAPIWebsocketTransport):
    """One phone call, as Asterisk's WebSocket channel delivers it."""

    def __init__(self, websocket: WebSocket, audio_in_filter: BaseAudioFilter | None = None):
        serializer = AsteriskSerializer()
        params = FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            audio_in_filter=audio_in_filter,
            serializer=serializer,
            fixed_audio_packet_size=PACKET_BYTES,
        )
        super().__init__(websocket, params)
        self._websocket = websocket
        self._output = PacedOutput(self, self._client, self._params, name=self._output_name)
        serializer.on_media_start = self._answered

    async def _on_client_connected(self, websocket: WebSocket) -> None:
        # The websocket is open, but the call isn't connected until Asterisk starts the media.
        return

    async def _answered(self, event: dict) -> None:
        logger.info(f"Phone call on {event.get('channel')} ({event.get('format')})")
        await self._call_event_handler("on_client_connected", self._websocket)


async def answer(websocket: WebSocket) -> None:
    """Run one phone call on a websocket Asterisk has opened."""
    from tellerline.agent.bot import NOISE_HANDLING, run_bot
    from tellerline.audio.noise import RNNoiseSuppressor

    requested = websocket.scope.get("subprotocols", [])
    await websocket.accept(subprotocol="media" if "media" in requested else None)
    transport = PhoneTransport(
        websocket, audio_in_filter=RNNoiseSuppressor() if NOISE_HANDLING else None
    )
    await run_bot(transport, WebSocketRunnerArguments(websocket=websocket), line="phone")


def mount_phone_line(app) -> None:
    """Accept Asterisk's calls at /phone on the agent's server."""
    app.add_api_websocket_route(PATH, answer)
