import asyncio

import pytest

from tellerline.agent import warm


@pytest.fixture(autouse=True)
def no_calls():
    warm._active_calls = 0
    yield
    warm._active_calls = 0


async def test_the_models_are_rewarmed_when_a_call_starts_alone():
    runs = []

    async def rewarm():
        runs.append(True)

    warm.call_started(rewarm)
    warm.call_started(rewarm)  # a second call while the first is on: models are in use
    await asyncio.sleep(0)
    await asyncio.gather(*warm._tasks)
    assert runs == [True]
    warm.call_ended()
    warm.call_ended()
    warm.call_started(rewarm)
    await asyncio.gather(*warm._tasks)
    assert runs == [True, True]


async def test_a_failed_rewarm_never_raises():
    async def broken():
        raise RuntimeError("server not running")

    warm.call_started(broken)
    await asyncio.gather(*warm._tasks)  # logged, not raised


def test_ending_more_calls_than_started_never_goes_negative():
    warm.call_ended()
    assert warm._active_calls == 0
