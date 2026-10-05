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
"""

from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    Frame,
    VADUserStartedSpeakingFrame,
)
from pipecat.turns.types import ProcessFrameResult
from pipecat.turns.user_start import MinWordsUserTurnStartStrategy
from pipecat.turns.user_start.base_user_turn_start_strategy import BaseUserTurnStartStrategy

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
