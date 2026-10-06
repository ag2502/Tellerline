"""When the caller's turn starts.

By whether the agent is talking:

- Agent silent: the caller's turn starts the moment voice activity is detected. Turn detection
  (Silero VAD, then Smart Turn) and transcription then run as soon as the caller stops.
- Agent talking: the caller has to say at least ``INTERRUPT_MIN_WORDS`` words to interrupt
  (Pipecat's ``MinWordsUserTurnStartStrategy``), so a cough, a door or a voice in the background
  doesn't cut the agent off.
- Agent just started, over a caller who was already talking again (they paused mid-sentence and
  carried on before the reply could reach them): voice activity is enough, as if the agent were
  silent. The VAD must have first heard that voice no later than ``FLOOR_FIRST_HEARD_S`` after
  the agent's first word, which the agent's own voice coming back down the line never is
  (``tellerline.agent.floor``).

Using the word count for every turn, as Phase 1 first did, starts the turn only once the
transcript exists, after the caller has already finished. Pipecat then waits out a fallback
timer before releasing the turn, which cost about 0.8 s on most replies.

The caller's turn ends when Smart Turn judges it finished, or after a 2 s fallback when it isn't
sure. Smart Turn judges everything the caller has said since they last heard the agent
(``ContinuingSmartTurn``), so a sentence they carried on after a pause is judged whole. A turn
whose transcript ends with a goodbye ends at once (``GoodbyeStopStrategy``): Smart Turn is often
unsure about a lone "Bye.", and those turns were the slowest of the latency gate.

Once the agent has ended the call, nothing the caller says starts a turn: a "bye" over the
agent's goodbye would otherwise cut it off and start another turn, and another goodbye. Pipecat's
user-mute strategies would also do that, but they drop the caller's audio, which then never
reaches the call recording.
"""

import re
import time
from collections.abc import Callable

from loguru import logger
from pipecat.audio.turn.base_turn_analyzer import EndOfTurnState
from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3
from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    Frame,
    TranscriptionFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
)
from pipecat.turns.types import ProcessFrameResult
from pipecat.turns.user_start import MinWordsUserTurnStartStrategy
from pipecat.turns.user_start.base_user_turn_start_strategy import BaseUserTurnStartStrategy
from pipecat.turns.user_stop.base_user_turn_stop_strategy import BaseUserTurnStopStrategy
from pipecat.turns.user_stop.turn_analyzer_user_turn_stop_strategy import (
    TurnAnalyzerUserTurnStopStrategy,
)

from tellerline.config import FLOOR_FIRST_HEARD_S, INTERRUPT_MIN_WORDS


def _never() -> bool:
    return False


def _unheard() -> float | None:
    return None


class VoiceStartStrategy(BaseUserTurnStartStrategy):
    """Start the caller's turn on voice activity when the floor is theirs: the agent is silent, or
    has only just started over a caller who was already talking. Never once the agent has ended
    the call.

    `heard_since` gives when (``time.time()``) the VAD first heard the voice it hears now.
    """

    def __init__(
        self,
        ending: Callable[[], bool] = _never,
        heard_since: Callable[[], float | None] = _unheard,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.agent_speaking = False
        self._agent_started_at = 0.0
        self._ending = ending
        self._heard_since = heard_since

    async def process_frame(self, frame: Frame) -> ProcessFrameResult:
        if isinstance(frame, BotStartedSpeakingFrame):
            if not self.agent_speaking:
                self._agent_started_at = time.time()
            self.agent_speaking = True
        elif isinstance(frame, BotStoppedSpeakingFrame):
            self.agent_speaking = False
        elif isinstance(frame, VADUserStartedSpeakingFrame) and not self._ending():
            if not self.agent_speaking or self._caller_was_first():
                await self.trigger_user_turn_started()
                return ProcessFrameResult.STOP
        return ProcessFrameResult.CONTINUE

    def _caller_was_first(self) -> bool:
        heard = self._heard_since()
        if heard is None or heard > self._agent_started_at + FLOOR_FIRST_HEARD_S:
            return False
        logger.debug(
            f"The caller was talking {(self._agent_started_at - heard) * 1000:+.0f} ms before the "
            "agent's reply began: their turn goes on"
        )
        return True


class MinWordsUnlessEndingStartStrategy(MinWordsUserTurnStartStrategy):
    """Pipecat's word-count rule for interrupting the agent, off once the agent has ended the
    call."""

    def __init__(self, ending: Callable[[], bool] = _never, **kwargs):
        super().__init__(**kwargs)
        self._ending = ending

    async def process_frame(self, frame: Frame) -> ProcessFrameResult:
        if self._ending():
            return ProcessFrameResult.CONTINUE
        return await super().process_frame(frame)


def turn_start_strategies(
    ending: Callable[[], bool] = _never, heard_since: Callable[[], float | None] = _unheard
) -> list[BaseUserTurnStartStrategy]:
    """Voice activity starts a turn when the floor is the caller's; words interrupt the agent
    otherwise; neither once `ending()` says the agent has ended the call."""
    return [
        VoiceStartStrategy(ending, heard_since),
        MinWordsUnlessEndingStartStrategy(ending, min_words=INTERRUPT_MIN_WORDS, use_interim=False),
    ]


_ENDS_WITH_GOODBYE = re.compile(
    r"\b(?:(?:good)?bye(?:[\s,.!]+(?:bye|now))*|cheers|see you|talk (?:to you )?soon|take care)"
    r"[\s,.!]*$",
    re.I,
)


class GoodbyeStopStrategy(BaseUserTurnStopStrategy):
    """End the caller's turn once they've stopped and their words end with a goodbye."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._in_turn = False
        self._speaking = False
        self._text = ""

    async def handle_user_turn_started(self):
        self._in_turn = True
        self._text = ""

    async def handle_user_turn_stopped(self):
        self._in_turn = False
        self._text = ""

    async def process_frame(self, frame: Frame) -> ProcessFrameResult:
        if isinstance(frame, VADUserStartedSpeakingFrame):
            self._speaking = True
        elif isinstance(frame, VADUserStoppedSpeakingFrame):
            self._speaking = False
        elif isinstance(frame, TranscriptionFrame) and self._in_turn:
            self._text = f"{self._text} {frame.text}".strip()
            if not self._speaking and _ENDS_WITH_GOODBYE.search(self._text):
                await self.trigger_user_turn_stopped()
        return ProcessFrameResult.CONTINUE


# How long the agent must have been talking before the caller has heard a reply. A reply the
# caller cut off sooner (they were talking first, ``VoiceStartStrategy``) is stopped about 0.4 s
# in, and what they say next continues their turn.
REPLY_HEARD_S = 1.0


class ContinuingSmartTurn(LocalSmartTurnAnalyzerV3):
    """Smart Turn on everything the caller has said since they last heard the agent.

    Pipecat's Smart Turn forgets a turn's audio once it has judged the turn complete. A caller who
    carried on after a pause, before hearing a reply (``tellerline.agent.floor``), then had the
    rest of their sentence judged on its own ("... and I was born on the 21st of November 1978"),
    which sounds unfinished: the agent waited out the 2 s fallback on 4 of 12 such calls. This
    analyzer keeps the earlier audio until the caller has heard a reply (``reply_heard``), so the
    whole sentence is judged; what they say once they've heard one is judged on its own.
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._kept = False  # the buffer holds a turn already judged complete
        self._resumed_at = 0.0  # when (time.monotonic()) the caller spoke again after it

    def append_audio(self, buffer: bytes, is_speech: bool) -> EndOfTurnState:
        if is_speech and self._kept and not self._speech_triggered and not self._resumed_at:
            self._resumed_at = time.monotonic()
        return super().append_audio(buffer, is_speech)

    def _clear(self, turn_state: EndOfTurnState):
        if turn_state == EndOfTurnState.COMPLETE and self._speech_start_time:
            # Keep the audio: the caller may carry on before they hear a reply.
            self._kept = True
            self._resumed_at = 0.0
            self._speech_triggered = False
            self._silence_ms = 0
            return
        self._kept = False
        self._resumed_at = 0.0
        super()._clear(turn_state)

    def reply_heard(self, since: float) -> None:
        """The caller has heard the agent's reply, which began at `since` (``time.monotonic()``):
        what they said before it was a finished turn."""
        if not self._kept:
            return
        self._audio_buffer = [(t, audio) for t, audio in self._audio_buffer if t >= since]
        self._speech_start_time = self._resumed_at if self._resumed_at >= since else 0
        self._kept = False
        self._resumed_at = 0.0


class WholeTurnStopStrategy(TurnAnalyzerUserTurnStopStrategy):
    """Pipecat's Smart Turn strategy, with ``ContinuingSmartTurn`` told when a reply was heard."""

    def __init__(self, **kwargs):
        super().__init__(turn_analyzer=ContinuingSmartTurn(), **kwargs)
        self._agent_started_at = 0.0

    async def process_frame(self, frame: Frame) -> ProcessFrameResult:
        if isinstance(frame, BotStartedSpeakingFrame):
            self._agent_started_at = self._agent_started_at or time.monotonic()
        elif isinstance(frame, BotStoppedSpeakingFrame):
            self._agent_started_at = 0.0
        elif self._agent_started_at and time.monotonic() - self._agent_started_at >= REPLY_HEARD_S:
            self._turn_analyzer.reply_heard(self._agent_started_at)
        return await super().process_frame(frame)


def turn_stop_strategies() -> list[BaseUserTurnStopStrategy]:
    """Smart Turn on the caller's whole turn, and a goodbye at the end of the caller's words."""
    return [WholeTurnStopStrategy(), GoodbyeStopStrategy()]
