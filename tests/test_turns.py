import time

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
    VoiceStartStrategy,
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
    strategy = VoiceStartStrategy()
    assert await started_turns(strategy, [VADUserStartedSpeakingFrame()]) == 1


async def test_voice_alone_does_not_interrupt_the_agent():
    strategy = VoiceStartStrategy()
    frames = [BotStartedSpeakingFrame(), VADUserStartedSpeakingFrame()]
    assert await started_turns(strategy, frames) == 0
    result = await strategy.process_frame(VADUserStartedSpeakingFrame())
    assert result == ProcessFrameResult.CONTINUE  # left to the word-count rule


async def test_voice_starts_the_turn_again_once_the_agent_stops():
    strategy = VoiceStartStrategy()
    frames = [BotStartedSpeakingFrame(), BotStoppedSpeakingFrame(), VADUserStartedSpeakingFrame()]
    assert await started_turns(strategy, frames) == 1


async def test_a_caller_who_was_talking_first_keeps_the_turn():
    # They carried on after a pause; the VAD heard them before the agent's reply began.
    heard = None
    strategy = VoiceStartStrategy(heard_since=lambda: heard)
    heard = time.time()
    await strategy.process_frame(BotStartedSpeakingFrame())
    assert await started_turns(strategy, [VADUserStartedSpeakingFrame()]) == 1


async def test_voice_heard_just_after_the_agent_began_still_counts_as_first():
    # The VAD notices a caller a moment after they start, and takes audio in bursts: voice it
    # first heard up to FLOOR_FIRST_HEARD_S after the reply began started before the reply could
    # reach them.
    heard = None
    strategy = VoiceStartStrategy(heard_since=lambda: heard)
    await strategy.process_frame(BotStartedSpeakingFrame())
    heard = time.time() + 0.05
    assert await started_turns(strategy, [VADUserStartedSpeakingFrame()]) == 1


async def test_voice_that_began_after_the_reply_needs_words():
    # Including the agent's own voice coming back down the line.
    heard = None
    strategy = VoiceStartStrategy(heard_since=lambda: heard)
    await strategy.process_frame(BotStartedSpeakingFrame())
    heard = time.time() + 0.5
    assert await started_turns(strategy, [VADUserStartedSpeakingFrame()]) == 0


async def test_the_agent_started_counts_from_its_first_word():
    # Pipecat sends BotStartedSpeakingFrame more than once; the reply began at the first.
    heard = time.time()
    strategy = VoiceStartStrategy(heard_since=lambda: heard)
    await strategy.process_frame(BotStartedSpeakingFrame())
    time.sleep(0.2)
    await strategy.process_frame(BotStartedSpeakingFrame())
    heard = time.time()
    assert await started_turns(strategy, [VADUserStartedSpeakingFrame()]) == 0


def test_interruptions_still_need_words():
    first, second = turn_start_strategies()
    assert isinstance(first, VoiceStartStrategy)
    assert isinstance(second, MinWordsUserTurnStartStrategy)


async def test_nothing_the_caller_says_starts_a_turn_once_the_call_has_ended():
    ending = False
    voice, words = turn_start_strategies(lambda: ending)
    assert await started_turns(voice, [VADUserStartedSpeakingFrame()]) == 1
    ending = True
    voice, words = turn_start_strategies(lambda: ending, lambda: time.time())
    assert await started_turns(voice, [VADUserStartedSpeakingFrame()]) == 0
    frames = [BotStartedSpeakingFrame(), VADUserStartedSpeakingFrame()]
    assert await started_turns(voice, frames) == 0
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
    from pipecat.turns.user_stop.turn_analyzer_user_turn_stop_strategy import (
        TurnAnalyzerUserTurnStopStrategy,
    )

    from tellerline.agent.turns import ContinuingSmartTurn

    first, second = turn_stop_strategies()
    assert isinstance(first, TurnAnalyzerUserTurnStopStrategy)
    assert isinstance(first._turn_analyzer, ContinuingSmartTurn)
    assert isinstance(second, GoodbyeStopStrategy)


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


@pytest.fixture
def judged(monkeypatch):
    """A ContinuingSmartTurn on a fake clock, and the seconds of audio each verdict judged."""
    from tellerline.agent.turns import ContinuingSmartTurn

    clock = Clock()
    monkeypatch.setattr(time, "monotonic", clock)
    analyzer = ContinuingSmartTurn()
    analyzer.set_sample_rate(16_000)
    seconds = []

    def predict(audio):
        seconds.append(len(audio) / 16_000)
        return {"prediction": 1, "probability": 0.9}

    monkeypatch.setattr(analyzer, "_predict_endpoint", predict)
    return analyzer, clock, seconds


def hear(analyzer, clock, seconds: float, speech: bool) -> None:
    for _ in range(round(seconds / 0.02)):
        clock.now += 0.02
        analyzer.append_audio(bytes(640), speech)


def verdict(analyzer):
    """What analyze_end_of_turn does, without the thread."""
    from pipecat.audio.turn.base_turn_analyzer import EndOfTurnState

    state, _ = analyzer._process_speech_segment(analyzer._audio_buffer)
    if state == EndOfTurnState.COMPLETE:
        analyzer._clear(state)
    return state


def test_a_sentence_carried_on_after_a_pause_is_judged_whole(judged):
    analyzer, clock, seconds = judged
    hear(analyzer, clock, 1.0, speech=True)  # "Sure, my customer number is 61023397,"
    hear(analyzer, clock, 0.2, speech=False)
    verdict(analyzer)
    analyzer.clear()  # the turn ends; the caller hears nothing yet
    hear(analyzer, clock, 0.5, speech=False)
    hear(analyzer, clock, 1.5, speech=True)  # "and I was born on the 21st of November 1978."
    hear(analyzer, clock, 0.2, speech=False)
    verdict(analyzer)
    assert seconds[0] < 1.6
    assert seconds[1] >= 3.2  # both halves and the pause between


def test_what_the_caller_says_after_hearing_a_reply_is_judged_alone(judged):
    analyzer, clock, seconds = judged
    hear(analyzer, clock, 1.0, speech=True)
    hear(analyzer, clock, 0.2, speech=False)
    verdict(analyzer)
    hear(analyzer, clock, 0.6, speech=False)
    reply_began = clock.now
    hear(analyzer, clock, 1.5, speech=False)  # the agent's reply
    analyzer.reply_heard(reply_began)
    hear(analyzer, clock, 1.0, speech=True)
    hear(analyzer, clock, 0.2, speech=False)
    verdict(analyzer)
    # Their words, with Smart Turn's half second before speech: not the earlier turn (4.5 s).
    assert seconds[1] < 2.0


def test_the_caller_cutting_in_on_a_reply_is_judged_from_where_they_began(judged):
    analyzer, clock, seconds = judged
    hear(analyzer, clock, 1.0, speech=True)
    hear(analyzer, clock, 0.2, speech=False)
    verdict(analyzer)
    reply_began = clock.now
    hear(analyzer, clock, 1.2, speech=False)
    hear(analyzer, clock, 0.4, speech=True)  # they start talking over the reply...
    analyzer.reply_heard(reply_began)  # ...which they've heard a second of
    hear(analyzer, clock, 0.6, speech=True)
    hear(analyzer, clock, 0.2, speech=False)
    verdict(analyzer)
    assert 1.1 <= seconds[1] < 2.0


async def test_smart_turn_hears_when_a_reply_was_heard(monkeypatch):
    from pipecat.frames.frames import TextFrame

    from tellerline.agent.turns import REPLY_HEARD_S, WholeTurnStopStrategy

    clock = Clock()
    strategy = WholeTurnStopStrategy()
    monkeypatch.setattr(time, "monotonic", clock)
    heard = []
    monkeypatch.setattr(strategy._turn_analyzer, "reply_heard", heard.append)
    began = clock.now
    await strategy.process_frame(BotStartedSpeakingFrame())
    clock.now += REPLY_HEARD_S / 2
    await strategy.process_frame(TextFrame("..."))
    assert heard == []  # cut off this soon, the caller hasn't heard a reply
    clock.now += REPLY_HEARD_S
    await strategy.process_frame(TextFrame("..."))
    assert heard == [began]
