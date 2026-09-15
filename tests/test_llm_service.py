from datetime import date

from pipecat.frames.frames import EndTaskFrame, LLMContextFrame, LLMTextFrame
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.tests.utils import run_test

from tellerline.actions import Action
from tellerline.brain import SinglePromptBrain
from tellerline.services.llm import (
    DIDNT_CATCH,
    NOT_VERIFIED_TRANSFER,
    TellerlineLLMService,
    last_user_text,
)

TODAY = date(2026, 9, 14)


class Chunk:
    def __init__(self, text):
        delta = type("Delta", (), {"content": text})()
        self.choices = [type("Choice", (), {"delta": delta})()]


class FakeStream:
    def __init__(self, pieces):
        self._pieces = list(pieces)
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._pieces:
            raise StopAsyncIteration
        return Chunk(self._pieces.pop(0))

    async def close(self):
        self.closed = True


class FakeCompletions:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    async def create(self, **kwargs):
        self.requests.append(kwargs)
        return FakeStream(self.responses.pop(0))


class FakeBank:
    def __init__(self, results):
        self.results = results
        self.calls: list[Action] = []

    async def run(self, action):
        self.calls.append(action)
        return self.results[action.tool]


def make_service(responses, bank_results, verified=True, **kwargs):
    brain = SinglePromptBrain(TODAY, verified=verified)
    bank = FakeBank(bank_results)
    service = TellerlineLLMService(
        brain=brain, bank=bank, model="test-model", today=TODAY, **kwargs
    )
    completions = FakeCompletions(responses)
    service._client = type(
        "Client", (), {"chat": type("Chat", (), {"completions": completions})()}
    )()
    return service, brain, bank, completions


def context_with(text):
    context = LLMContext()
    context.add_message({"role": "user", "content": text})
    return context


async def spoken_text(service, *texts):
    frames = [LLMContextFrame(context_with(text)) for text in texts]
    down, up = await run_test(service, frames_to_send=frames)
    return "".join(f.text for f in down if isinstance(f, LLMTextFrame)), up


def test_last_user_text_handles_string_and_parts():
    context = LLMContext()
    context.add_message({"role": "user", "content": [{"type": "text", "text": "Hi there"}]})
    context.add_message({"role": "assistant", "content": "Hello"})
    assert last_user_text(context) == "Hi there"


async def test_speech_streams_straight_through():
    service, brain, bank, completions = make_service(
        [["Could I have ", "the last four digits?"]], {}
    )
    text, _ = await spoken_text(service, "I lost my card")
    assert text == "Could I have the last four digits?"
    assert bank.calls == []
    assert completions.requests[0]["stop"] == ["\n"]
    assert brain.history[-1]["content"] == "Could I have the last four digits?"


async def test_action_runs_against_the_bank_and_speaks_the_template():
    service, brain, bank, _ = make_service(
        [["ACTION balance ", "account=current"]],
        {"get_balance": {"balance_eur": 12.5, "available_eur": 12.5}},
    )
    text, _ = await spoken_text(service, "What's my balance?")
    assert bank.calls == [Action("get_balance", {"account": "current"})]
    assert text == "The balance on your current account is twelve euro and fifty cent."
    assert "ACTION" not in brain.history[-1]["content"]


async def test_incomplete_action_becomes_a_question_without_calling_the_bank():
    service, _, bank, _ = make_service([["ACTION freeze reason=lost"]], {})
    text, _ = await spoken_text(service, "Freeze my card")
    assert text == "What are the last four digits of the card?"
    assert bank.calls == []


async def test_disallowed_action_is_not_run():
    service, _, bank, _ = make_service([["ACTION balance account=current"]], {}, verified=False)
    text, _ = await spoken_text(service, "What's my balance?")
    assert text == DIDNT_CATCH
    assert bank.calls == []


async def test_repeated_failed_verification_transfers_the_caller():
    bank_results = {
        "verify_identity": {"verified": False},
        "transfer_to_human": {"status": "queued"},
    }
    line = ["ACTION verify customer=12345678 dob=1990-01-01"]
    service, brain, bank, _ = make_service(
        [line, line], bank_results, verified=False, max_failed_verifications=2
    )
    text, up = await spoken_text(service, "12345678, 1 January 1990", "12345678, 1 January 1990")
    assert NOT_VERIFIED_TRANSFER in text
    assert not brain.verified
    assert any(isinstance(frame, EndTaskFrame) for frame in up)
    assert [call.tool for call in bank.calls][-1] == "transfer_to_human"
