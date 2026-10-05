"""When the caller's turn starts and ends.

Starting, by whether the agent is talking:

- Agent silent: the caller's turn starts the moment voice activity is detected. Turn detection
  (Silero VAD, then Smart Turn) and transcription then run as soon as the caller stops.
- Agent talking: the caller has to say at least ``INTERRUPT_MIN_WORDS`` words to interrupt
  (Pipecat's ``MinWordsUserTurnStartStrategy``), so a cough, a door or a voice in the background
  doesn't cut the agent off.

Using the word count for every turn, as Phase 1 first did, starts the turn only once the
transcript exists, after the caller has already finished. Pipecat then waits out a fallback
timer before releasing the turn, which cost about 0.8 s on most replies.

Ending: Smart Turn v3.2 judges from the audio whether the caller has finished. When it judges
them unfinished, Pipecat waits for more speech, for up to ``USER_TURN_STOP_TIMEOUT_S`` (2 s).
Parakeet hears the same audio and punctuates its transcript, so when that transcript ends a
sentence of at least ``PUNCTUATED_MIN_WORDS`` words ("Okay, and the missing card ends 7314."),
the caller has most likely finished: the turn is released after ``PUNCTUATED_GRACE_S`` instead,
unless they start speaking again. Shorter fragments ("Actually.", "My customer number.") are
often a pause mid-sentence, so Smart Turn's doubt stands.
"""

import asyncio
import re

from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3
from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    Frame,
    TranscriptionFrame,
    VADUserStartedSpeakingFrame,
)
from pipecat.turns.types import ProcessFrameResult
from pipecat.turns.user_start import MinWordsUserTurnStartStrategy
from pipecat.turns.user_start.base_user_turn_start_strategy import BaseUserTurnStartStrategy
from pipecat.turns.user_stop import TurnAnalyzerUserTurnStopStrategy

from tellerline.config import INTERRUPT_MIN_WORDS, PUNCTUATED_GRACE_S, PUNCTUATED_MIN_WORDS

_ENDS_SENTENCE = re.compile(r"[.?!][\"')\]]*\s*$")


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


class TranscriptAwareTurnStopStrategy(TurnAnalyzerUserTurnStopStrategy):
    """Smart Turn decides the caller has finished, with Parakeet's punctuation as a second opinion.

    Built on Pipecat's strategy and its turn-scoped state (pinned to pipecat-ai 1.10).
    """

    def __init__(self, *, grace_s: float = PUNCTUATED_GRACE_S, **kwargs):
        kwargs.setdefault("turn_analyzer", LocalSmartTurnAnalyzerV3())
        super().__init__(**kwargs)
        self._grace_s = grace_s
        self._grace_task: asyncio.Task | None = None

    async def _handle_transcription(self, frame: TranscriptionFrame):
        await super()._handle_transcription(frame)
        doubted = self._vad_stopped and not self._turn_complete
        sentence = _ENDS_SENTENCE.search(self._text) and (
            len(self._text.split()) >= PUNCTUATED_MIN_WORDS
        )
        if frame.finalized and doubted and sentence:
            await self._cancel_grace()
            self._grace_task = self.task_manager.create_task(
                self._release_after_grace(), f"{self}::punctuated_grace"
            )

    async def _release_after_grace(self):
        try:
            await asyncio.sleep(self._grace_s)
        except asyncio.CancelledError:
            return
        self._grace_task = None
        if self._vad_stopped and not self._vad_user_speaking and not self._turn_complete:
            self._turn_complete = True
            await self._maybe_trigger_user_turn_stopped()

    async def _discard_pending_end_of_turn(self):
        await super()._discard_pending_end_of_turn()
        await self._cancel_grace()

    async def _cancel_grace(self):
        if self._grace_task is not None:
            await self.task_manager.cancel_task(self._grace_task)
            self._grace_task = None

    async def cleanup(self):
        await self._cancel_grace()
        await super().cleanup()


def turn_stop_strategies() -> list[TurnAnalyzerUserTurnStopStrategy]:
    return [TranscriptAwareTurnStopStrategy()]
