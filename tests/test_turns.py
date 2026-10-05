from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    VADUserStartedSpeakingFrame,
)
from pipecat.turns.types import ProcessFrameResult
from pipecat.turns.user_start import MinWordsUserTurnStartStrategy

from tellerline.agent.turns import VADWhenAgentSilentStartStrategy, turn_start_strategies


async def started_turns(strategy, frames) -> int:
    started = []

    @strategy.event_handler("on_user_turn_started")
    async def on_started(*args, **kwargs):
        started.append(True)

    for frame in frames:
        await strategy.process_frame(frame)
    return len(started)


async def test_voice_starts_the_turn_when_the_agent_is_silent():
    strategy = VADWhenAgentSilentStartStrategy()
    assert await started_turns(strategy, [VADUserStartedSpeakingFrame()]) == 1


async def test_voice_alone_does_not_interrupt_the_agent():
    strategy = VADWhenAgentSilentStartStrategy()
    frames = [BotStartedSpeakingFrame(), VADUserStartedSpeakingFrame()]
    assert await started_turns(strategy, frames) == 0
    result = await strategy.process_frame(VADUserStartedSpeakingFrame())
    assert result == ProcessFrameResult.CONTINUE  # left to the word-count rule


async def test_voice_starts_the_turn_again_once_the_agent_stops():
    strategy = VADWhenAgentSilentStartStrategy()
    frames = [BotStartedSpeakingFrame(), BotStoppedSpeakingFrame(), VADUserStartedSpeakingFrame()]
    assert await started_turns(strategy, frames) == 1


def test_interruptions_still_need_words():
    first, second = turn_start_strategies()
    assert isinstance(first, VADWhenAgentSilentStartStrategy)
    assert isinstance(second, MinWordsUserTurnStartStrategy)


class DoubtfulAnalyzer:
    """A turn analyzer that always thinks the caller hasn't finished."""

    params = None

    def set_sample_rate(self, rate):
        pass

    def update_vad_start_secs(self, secs):
        pass

    def append_audio(self, buffer, is_speech):
        from pipecat.audio.turn.base_turn_analyzer import EndOfTurnState

        return EndOfTurnState.INCOMPLETE

    async def analyze_end_of_turn(self):
        from pipecat.audio.turn.base_turn_analyzer import EndOfTurnState

        return EndOfTurnState.INCOMPLETE, None

    def clear(self):
        pass

    async def cleanup(self):
        pass


async def stop_strategy(grace_s=0.05):
    from unittest.mock import MagicMock

    from pipecat.processors.frame_processor import FrameProcessorSetup
    from pipecat.utils.asyncio.task_manager import TaskManager

    from tellerline.agent.turns import TranscriptAwareTurnStopStrategy

    strategy = TranscriptAwareTurnStopStrategy(turn_analyzer=DoubtfulAnalyzer(), grace_s=grace_s)
    setup = FrameProcessorSetup(clock=MagicMock(), task_manager=TaskManager(), pipeline_worker=None)
    await strategy.setup(setup)
    stopped = []

    @strategy.event_handler("on_user_turn_stopped")
    async def on_stopped(*args, **kwargs):
        stopped.append(True)

    return strategy, stopped


async def test_a_doubted_turn_ending_a_sentence_is_released_after_the_grace():
    import asyncio

    from pipecat.frames.frames import TranscriptionFrame, VADUserStoppedSpeakingFrame

    strategy, stopped = await stop_strategy()
    await strategy.process_frame(VADUserStoppedSpeakingFrame(stop_secs=0.2))
    said = "Okay, and the missing card ends 7314."
    await strategy.process_frame(TranscriptionFrame(said, "caller", "now", finalized=True))
    assert not stopped  # Smart Turn doubted it: not straight away
    await asyncio.sleep(0.1)
    assert stopped


async def test_a_doubted_turn_without_a_full_stop_keeps_waiting():
    import asyncio

    from pipecat.frames.frames import TranscriptionFrame, VADUserStoppedSpeakingFrame

    strategy, stopped = await stop_strategy()
    await strategy.process_frame(VADUserStoppedSpeakingFrame(stop_secs=0.2))
    said = "My customer number is"
    await strategy.process_frame(TranscriptionFrame(said, "caller", "now", finalized=True))
    await asyncio.sleep(0.1)
    assert not stopped


async def test_speaking_again_during_the_grace_cancels_the_release():
    import asyncio

    from pipecat.frames.frames import (
        TranscriptionFrame,
        VADUserStartedSpeakingFrame,
        VADUserStoppedSpeakingFrame,
    )

    strategy, stopped = await stop_strategy()
    await strategy.process_frame(VADUserStoppedSpeakingFrame(stop_secs=0.2))
    said = "My customer number is 45127890."
    await strategy.process_frame(TranscriptionFrame(said, "caller", "now", finalized=True))
    await strategy.process_frame(VADUserStartedSpeakingFrame())
    await asyncio.sleep(0.1)
    assert not stopped
