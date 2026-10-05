from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    VADUserStartedSpeakingFrame,
)
from pipecat.turns.types import ProcessFrameResult
from pipecat.turns.user_start import MinWordsUserTurnStartStrategy

from tellerline.agent.turns import (
    MuteWhileEndingStrategy,
    VADWhenAgentSilentStartStrategy,
    turn_start_strategies,
)


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


async def test_the_caller_is_muted_once_the_agent_has_ended_the_call():
    ending = False
    strategy = MuteWhileEndingStrategy(lambda: ending)
    assert await strategy.process_frame(VADUserStartedSpeakingFrame()) is False
    ending = True
    assert await strategy.process_frame(VADUserStartedSpeakingFrame()) is True
