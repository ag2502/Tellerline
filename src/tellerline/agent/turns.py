"""When the caller's turn starts.

By whether the agent is talking:

- Agent silent: the caller's turn starts the moment voice activity is detected. Turn detection
  (Silero VAD, then Smart Turn) and transcription then run as soon as the caller stops.
- Agent talking: the caller has to say at least ``INTERRUPT_MIN_WORDS`` words to interrupt
  (Pipecat's ``MinWordsUserTurnStartStrategy``), so a cough, a door or a voice in the background
  doesn't cut the agent off.

Using the word count for every turn, as Phase 1 first did, starts the turn only once the
transcript exists, after the caller has already finished. Pipecat then waits out a fallback
timer before releasing the turn, which cost about 0.8 s on most replies.

The caller's turn ends when Smart Turn judges it finished, or after a 2 s fallback when it isn't
sure. A turn whose transcript ends with a goodbye ends at once (``GoodbyeStopStrategy``): Smart
Turn is often unsure about a lone "Bye.", and those turns were the slowest of the latency gate.

Once the agent has ended the call, the caller is muted (``MuteWhileEndingStrategy``): a "bye"
over the agent's goodbye would otherwise cut it off and start another turn, and another goodbye.
"""

import re
from collections.abc import Callable

from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    Frame,
    TranscriptionFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
)
from pipecat.turns.types import ProcessFrameResult
from pipecat.turns.user_mute.base_user_mute_strategy import BaseUserMuteStrategy
from pipecat.turns.user_start import MinWordsUserTurnStartStrategy
from pipecat.turns.user_start.base_user_turn_start_strategy import BaseUserTurnStartStrategy
from pipecat.turns.user_stop.base_user_turn_stop_strategy import BaseUserTurnStopStrategy
from pipecat.turns.user_turn_strategies import default_user_turn_stop_strategies

from tellerline.config import INTERRUPT_MIN_WORDS


class VADWhenAgentSilentStartStrategy(BaseUserTurnStartStrategy):
    """Start the caller's turn on voice activity, unless the agent is talking."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.agent_speaking = False

    async def process_frame(self, frame: Frame) -> ProcessFrameResult:
        if isinstance(frame, BotStartedSpeakingFrame):
            self.agent_speaking = True
        elif isinstance(frame, BotStoppedSpeakingFrame):
            self.agent_speaking = False
        elif isinstance(frame, VADUserStartedSpeakingFrame) and not self.agent_speaking:
            await self.trigger_user_turn_started()
            return ProcessFrameResult.STOP
        return ProcessFrameResult.CONTINUE


def turn_start_strategies() -> list[BaseUserTurnStartStrategy]:
    """Voice activity starts a turn when the agent is silent; words interrupt it when it isn't."""
    return [
        VADWhenAgentSilentStartStrategy(),
        MinWordsUserTurnStartStrategy(min_words=INTERRUPT_MIN_WORDS, use_interim=False),
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


def turn_stop_strategies() -> list[BaseUserTurnStopStrategy]:
    """Smart Turn (Pipecat's default), and a goodbye at the end of the caller's words."""
    return [*default_user_turn_stop_strategies(), GoodbyeStopStrategy()]


class MuteWhileEndingStrategy(BaseUserMuteStrategy):
    """Mute the caller while the agent says its last words on a call it has ended."""

    def __init__(self, ending: Callable[[], bool], **kwargs):
        super().__init__(**kwargs)
        self._ending = ending

    async def process_frame(self, frame: Frame) -> bool:
        await super().process_frame(frame)
        return self._ending()
