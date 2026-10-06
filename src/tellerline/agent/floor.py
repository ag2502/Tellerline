"""Who has the floor: the agent doesn't start a reply over a caller who has carried on.

A caller who pauses mid-sentence ("Pause my card ending 7780 for a bit, ... it's somewhere in the
house.") can sound finished to Smart Turn, and the agent's reply is ready 0.9-1.1 s after the
pause began. Over 47 such pauses in the benchmark's caller lines (D-033), the caller carried on
after 0.33-0.76 s: often before the reply began, but before the VAD had confirmed it was speech
(0.32 s after they carried on, p90 0.46 s, with ``tellerline.audio.vad``). A reply that starts in
between talks over the caller, who then has to say two more words to stop it
(``INTERRUPT_MIN_WORDS``), and answers half a sentence.

Two rules give the caller the floor back:

- The first word of a reply waits while the VAD can hear the caller (``FloorGate``): it notices
  them 0.06 s after they carry on (p90 0.10 s). If the VAD confirms they're talking, their turn
  starts again and the reply is dropped before a word of it was said; if the sound dies away (a
  breath, a cough), the reply goes out at once.
- A caller the VAD first heard no later than ``FLOOR_FIRST_HEARD_S`` after the agent's first word
  was talking before the reply could reach them: when the VAD confirms it, their turn starts and
  the reply stops, without waiting for words (``tellerline.agent.turns``).

Either way the agent then answers everything the caller said since it was last heard, as one
turn, and forgets the reply nobody heard (``TellerlineLLMService``); Smart Turn judges the whole
sentence too (``ContinuingSmartTurn``).
"""

import asyncio
import time
from collections.abc import Callable

from loguru import logger
from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    CancelFrame,
    Frame,
    InterruptionFrame,
    OutputAudioRawFrame,
    SystemFrame,
)
from pipecat.processors.frame_processor import FrameDirection, FrameProcessor

from tellerline.config import FLOOR_HOLD_MAX_S, FLOOR_QUIET_S


class FloorGate(FrameProcessor):
    """Holds the first audio of a reply while the caller can be heard.

    Placed just before the output transport. Only the start of a reply waits: once the agent is
    talking, interrupting it is the turn strategies' business.
    """

    def __init__(
        self,
        hears_caller: Callable[[], bool],
        *,
        agent_speaking: Callable[[bool], None] | None = None,
        max_hold_s: float = FLOOR_HOLD_MAX_S,
        quiet_s: float = FLOOR_QUIET_S,
        poll_s: float = 0.01,
        **kwargs,
    ):
        """`hears_caller` says whether the VAD can hear the caller now; `agent_speaking` is told
        when the agent starts and stops talking."""
        super().__init__(**kwargs)
        self._hears_caller = hears_caller
        self._tell_agent_speaking = agent_speaking
        self._max_hold_s = max_hold_s
        self._quiet_s = quiet_s
        self._poll_s = poll_s
        self._agent_speaking = False
        self._held: list[Frame] = []
        self._holding = False
        self._watch: asyncio.Task | None = None

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, (BotStartedSpeakingFrame, BotStoppedSpeakingFrame)):
            self._agent_speaking = isinstance(frame, BotStartedSpeakingFrame)
            if self._tell_agent_speaking is not None:
                self._tell_agent_speaking(self._agent_speaking)

        if direction == FrameDirection.UPSTREAM:
            await self.push_frame(frame, direction)
        elif isinstance(frame, (InterruptionFrame, CancelFrame)):
            # The caller has taken the turn (or the call is over): nothing held is said.
            await self._drop()
            await self.push_frame(frame, direction)
        elif isinstance(frame, SystemFrame):
            await self.push_frame(frame, direction)
        elif self._holding:
            self._held.append(frame)
        elif (
            isinstance(frame, OutputAudioRawFrame)
            and not self._agent_speaking
            and self._hears_caller()
        ):
            self._holding = True
            self._held.append(frame)
            self._watch = self.create_task(self._hold())
        else:
            await self.push_frame(frame, direction)

    async def cleanup(self):
        await super().cleanup()
        await self._drop()

    async def _hold(self) -> None:
        started = time.monotonic()
        quiet_since: float | None = None
        while True:
            await asyncio.sleep(self._poll_s)
            now = time.monotonic()
            if self._hears_caller():
                quiet_since = None
            elif quiet_since is None:
                quiet_since = now
            if quiet_since is not None and now - quiet_since >= self._quiet_s:
                reason = "the caller went quiet"
                break
            if now - started >= self._max_hold_s:
                reason = "held as long as it may be"
                break
        logger.debug(f"Reply held {(now - started) * 1000:.0f} ms over the caller: {reason}")
        # Frames arriving meanwhile join the queue, so everything goes out in order.
        while self._held:
            await self.push_frame(self._held.pop(0))
        self._holding = False
        self._watch = None

    async def _drop(self) -> None:
        if self._held:
            logger.debug("Reply dropped before a word of it was said: the caller carried on")
        self._held.clear()
        self._holding = False
        if self._watch is not None:
            watch, self._watch = self._watch, None
            await self.cancel_task(watch)
