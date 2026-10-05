import asyncio
import time

import numpy as np

import bench.caller as caller
from bench.caller import BotEar, as_spoken, converse


def test_customer_and_card_numbers_are_spoken_digit_by_digit():
    assert as_spoken("My customer number is 48210573.") == "My customer number is 4 8 2 1 0 5 7 3."
    assert as_spoken("It's 4512 7890, born 1985.") == "It's 4 5 1 2 7 8 9 0, born 1985."
    assert as_spoken("My card ending 4217 was stolen") == "My card ending 4 2 1 7 was stolen"
    assert as_spoken("It ends in 2210.") == "It ends in 2 2 1 0."


def test_years_and_amounts_are_left_alone():
    assert (
        as_spoken("Born the 2nd of May 1987, charged 22.50")
        == "Born the 2nd of May 1987, charged 22.50"
    )


class FakeLine:
    """A line where the agent greets at once and answers each caller line `delay_s` after it."""

    def __init__(self, ear: BotEar, delay_s: float, overlap_on: int | None = None):
        self.ear = ear
        self.delay_s = delay_s
        self.overlap_on = overlap_on
        self.said = 0
        now = time.perf_counter()
        ear.onsets.append(now)
        ear.last_sound = now

    def say(self, pcm):
        future = asyncio.get_running_loop().create_future()
        end = time.perf_counter() + 0.01
        if self.said == self.overlap_on:
            self.ear.onsets.append(end - 0.005)  # the agent cut in before the line ended
        self.ear.onsets.append(end + self.delay_s)
        self.ear.last_sound = end + self.delay_s
        self.said += 1
        asyncio.get_running_loop().call_later(0.01, future.set_result, end)
        return future


async def test_converse_times_each_reply_from_the_end_of_the_caller_speech(monkeypatch):
    monkeypatch.setattr(caller, "CALLER_PAUSE_S", 0.0)
    monkeypatch.setattr(caller, "BOT_DONE_SILENCE_S", 0.02)
    monkeypatch.setattr(caller, "REPLY_TIMEOUT_S", 1.0)
    ear = BotEar()
    line = FakeLine(ear, delay_s=0.03, overlap_on=1)
    # Cut-ins only count after the first 0.3 s of the caller's line, so "two" lasts a second.
    audio = {"one": np.zeros(160, np.int16), "two": np.zeros(8_000, np.int16)}
    turns = await converse(line.say, ear, ["one", "two", "one"], audio, 8_000, lambda: True)
    assert [t["turn"] for t in turns] == [0, 1, 2]
    assert turns[0]["caller_speech_s"] == 0.02
    assert abs(turns[0]["latency_s"] - 0.03) < 0.005
    assert turns[1]["overlap"] is True and turns[1]["latency_s"] is None
    assert turns[0]["agent"] is None  # this line carries no reports


async def test_converse_stops_when_the_line_drops(monkeypatch):
    monkeypatch.setattr(caller, "CALLER_PAUSE_S", 0.0)
    monkeypatch.setattr(caller, "BOT_DONE_SILENCE_S", 0.02)
    ear = BotEar()
    line = FakeLine(ear, delay_s=0.03)
    audio = {"one": np.zeros(160, np.int16)}
    turns = await converse(line.say, ear, ["one", "one"], audio, 8_000, lambda: line.said < 1)
    assert len(turns) == 1
