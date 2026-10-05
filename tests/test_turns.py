import pytest
from pipecat.frames.frames import (
    BotStartedSpeakingFrame,
    BotStoppedSpeakingFrame,
    TranscriptionFrame,
    VADUserStartedSpeakingFrame,
    VADUserStoppedSpeakingFrame,
)
from pipecat.turns.types import ProcessFrameResult
from pipecat.turns.user_start import MinWordsUserTurnStartStrategy

from tellerline.agent.turns import (
    GoodbyeStopStrategy,
    VADWhenAgentSilentStartStrategy,
    turn_start_strategies,
    turn_stop_strategies,
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


async def test_nothing_the_caller_says_starts_a_turn_once_the_call_has_ended():
    ending = False
    voice, words = turn_start_strategies(lambda: ending)
    assert await started_turns(voice, [VADUserStartedSpeakingFrame()]) == 1
    ending = True
    voice, words = turn_start_strategies(lambda: ending)
    assert await started_turns(voice, [VADUserStartedSpeakingFrame()]) == 0
    frames = [BotStartedSpeakingFrame(), TranscriptionFrame("Thanks, bye", "caller", "now")]
    assert await started_turns(words, frames) == 0


async def stopped_after(words: str, still_speaking: bool = False) -> bool:
    strategy = GoodbyeStopStrategy()
    stopped = []

    @strategy.event_handler("on_user_turn_stopped")
    async def on_stopped(*args, **kwargs):
        stopped.append(True)

    await strategy.handle_user_turn_started()
    await strategy.process_frame(VADUserStartedSpeakingFrame())
    if not still_speaking:
        await strategy.process_frame(VADUserStoppedSpeakingFrame())
    await strategy.process_frame(TranscriptionFrame(words, "caller", "now"))
    return bool(stopped)


@pytest.mark.parametrize(
    "words",
    ["No, it's fine. Bye.", "Thanks, bye bye!", "That's all, bye now.", "Grand, cheers."],
)
async def test_a_turn_that_ends_with_a_goodbye_ends_at_once(words):
    assert await stopped_after(words)


@pytest.mark.parametrize("words", ["No, it's fine.", "Bye the way, my card", "Goodbye to my card"])
async def test_other_turns_wait_for_smart_turn(words):
    assert not await stopped_after(words)


async def test_a_goodbye_while_the_caller_is_still_talking_waits():
    assert not await stopped_after("Thanks, bye.", still_speaking=True)


def test_smart_turn_still_decides_every_other_turn():
    first, second = turn_stop_strategies()
    assert type(first).__name__ == "TurnAnalyzerUserTurnStopStrategy"
    assert isinstance(second, GoodbyeStopStrategy)
