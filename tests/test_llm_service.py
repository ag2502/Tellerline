from datetime import date

import pytest
from pipecat.frames.frames import (
    BotStoppedSpeakingFrame,
    EndWorkerFrame,
    LLMContextAssistantTurnFrame,
    LLMContextFrame,
    LLMTextFrame,
)
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.tests.utils import SleepFrame, run_test

from tellerline.actions import Action
from tellerline.brain import SinglePromptBrain
from tellerline.services.llm import (
    DIDNT_CATCH,
    NOT_VERIFIED_TRANSFER,
    VERIFY_FIRST,
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
        brain=brain, bank=bank, model="test-model", today=TODAY, **{"end_grace_s": 0.0, **kwargs}
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


async def spoken_text(service, *texts, then=()):
    frames = [LLMContextFrame(context_with(text)) for text in texts] + list(then)
    down, up = await run_test(service, frames_to_send=frames)
    return "".join(f.text for f in down if isinstance(f, LLMTextFrame)), up


# The agent finishing its last sentence, and a moment for the hang-up to follow.
SPOKEN = (SleepFrame(0.05), BotStoppedSpeakingFrame(), SleepFrame(0.05))


def test_last_user_text_handles_string_and_parts():
    context = LLMContext()
    context.add_message({"role": "user", "content": "Earlier question"})
    context.add_message({"role": "assistant", "content": "Hello"})
    context.add_message({"role": "user", "content": [{"type": "text", "text": "Hi there"}]})
    assert last_user_text(context) == "Hi there"


def test_nothing_new_from_the_caller_gives_empty_text():
    context = LLMContext()
    context.add_message({"role": "user", "content": "Hi"})
    context.add_message({"role": "assistant", "content": "Hello"})
    assert last_user_text(context) == ""


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
    assert text == "On your current account, the balance is twelve euro and fifty cent."
    assert "ACTION" not in brain.history[-1]["content"]


async def test_incomplete_action_becomes_a_question_without_calling_the_bank():
    service, _, bank, _ = make_service([["ACTION freeze reason=lost"]], {})
    text, _ = await spoken_text(service, "Freeze my card")
    assert text == "What are the last four digits of the card?"
    assert bank.calls == []


async def test_banking_before_verification_asks_for_the_callers_details():
    service, _, bank, _ = make_service([["ACTION balance account=current"]], {}, verified=False)
    text, _ = await spoken_text(service, "What's my balance?")
    assert text == VERIFY_FIRST
    assert bank.calls == []


async def test_unknown_action_line_asks_the_caller_to_repeat():
    service, _, bank, _ = make_service([["ACTION teleport card=4217"]], {})
    text, _ = await spoken_text(service, "Do something")
    assert text == DIDNT_CATCH
    assert bank.calls == []


async def test_a_card_the_caller_never_said_is_asked_for_not_used():
    # Phase 1 held-out failure: the model took the last four digits of the customer number.
    service, _, bank, _ = make_service([["ACTION freeze card=7890 reason=lost"]], {})
    text, _ = await spoken_text(service, "I found the card I lost, can you switch it back on?")
    assert text == "What are the last four digits of the card?"
    assert bank.calls == []


async def test_a_date_the_caller_never_said_is_asked_for_not_used():
    # Phone demo failure: cut off after "It was thirty-four euro", the model supplied a date.
    service, _, bank, _ = make_service(
        [['ACTION dispute merchant="Corrib Taxis" amount=34 date=2026-09-29']], {}
    )
    text, _ = await spoken_text(service, "It was thirty-four euro.")
    assert text == "Could you tell me the date it went out, please?"
    assert bank.calls == []


async def test_a_date_the_caller_did_say_reaches_the_bank():
    service, _, bank, _ = make_service(
        [['ACTION dispute merchant="Corrib Taxis" amount=34.60 date=2026-09-03']],
        {"dispute_transaction": {"reference": "DSP20417", "status": "opened"}},
    )
    await spoken_text(service, "It was 34 euro and 60 cent on the 3rd of September.")
    assert [call.arguments["date"] for call in bank.calls] == ["2026-09-03"]


async def test_the_model_hears_exact_amounts_and_dates():
    service, _, _, completions = make_service([["Who was the payment to?"]], {})
    await spoken_text(service, "It was 34 euro 60, yesterday.")
    assert (
        completions.requests[0]["messages"][-1]["content"]
        == "It was €34.60, yesterday (2026-09-13)."
    )


async def test_repeated_failed_verification_transfers_the_caller():
    bank_results = {
        "verify_identity": {"verified": False},
        "transfer_to_human": {"status": "queued"},
    }
    line = ["ACTION verify customer=12345678 dob=1990-01-01"]
    service, brain, bank, _ = make_service(
        [line, line], bank_results, verified=False, max_failed_verifications=2
    )
    text, up = await spoken_text(
        service, "12345678, 1 January 1990", "12345678, 1 January 1990", then=SPOKEN
    )
    assert NOT_VERIFIED_TRANSFER in text
    assert not brain.verified
    assert any(isinstance(frame, EndWorkerFrame) for frame in up)
    assert [call.tool for call in bank.calls][-1] == "transfer_to_human"


def test_fragments_since_the_agent_last_spoke_are_joined():
    context = LLMContext()
    context.add_message({"role": "assistant", "content": "How can I help?"})
    context.add_message({"role": "user", "content": "My customer number is 45127890."})
    context.add_message({"role": "user", "content": "and my date of birth"})
    context.add_message({"role": "user", "content": "is the 3rd of March 1991."})
    assert last_user_text(context) == (
        "My customer number is 45127890. and my date of birth is the 3rd of March 1991."
    )


async def test_the_call_ends_only_after_a_goodbye():
    service, _, bank, _ = make_service([["ACTION end"]], {})
    text, up = await spoken_text(service, "No, I'm sure it'll turn up.")
    assert text == "No problem. Is there anything else I can help with?"
    assert not any(isinstance(frame, EndWorkerFrame) for frame in up)

    service, _, bank, _ = make_service([["ACTION end"]], {"end_call": {"status": "ending"}})
    text, up = await spoken_text(service, "Grand, that's all I needed. Cheers.")
    assert text == "Thanks for calling Tellerline Bank. Goodbye."
    # Not yet: hanging up now would cut the goodbye off before the caller hears it.
    assert not any(isinstance(frame, EndWorkerFrame) for frame in up)

    service, _, bank, _ = make_service([["ACTION end"]], {"end_call": {"status": "ending"}})
    text, up = await spoken_text(service, "Grand, that's all I needed. Cheers.", then=SPOKEN)
    assert [type(frame) for frame in up].count(EndWorkerFrame) == 1
    # The call stays ended while the pipeline finishes: a "bye" now starts no new turn.
    assert service.ending


async def test_a_turn_heard_in_pieces_is_decided_on_the_whole_transcript():
    # Transcribed segment by segment the goodbye was lost; transcribed whole, it's there.
    async def whole_turn(text):
        assert text == "That's everything, thanks."
        return "That's everything, thanks. Bye."

    service, _, bank, _ = make_service(
        [["ACTION end"]], {"end_call": {"status": "ending"}}, whole_turn=whole_turn
    )
    text, _ = await spoken_text(service, "That's everything, thanks.")
    assert text == "Thanks for calling Tellerline Bank. Goodbye."
    assert [call.tool for call in bank.calls] == ["end_call"]


async def test_nothing_is_answered_after_the_goodbye():
    # Demo-call failure: "Thanks, bye" began before the goodbye turn was handled, and got a
    # second goodbye.
    service, _, bank, _ = make_service(
        [["ACTION end"], ["ACTION end"]], {"end_call": {"status": "ending"}}
    )
    text, _ = await spoken_text(service, "No, that's everything.", "Thanks, bye.")
    assert text == "Thanks for calling Tellerline Bank. Goodbye."
    assert [call.tool for call in bank.calls] == ["end_call"]


@pytest.mark.parametrize(
    "hello", ["Hi, it's Naim.", "Hello?", "Good morning, this is Seán Murphy."]
)
async def test_a_caller_who_has_only_said_hello_is_not_transferred(hello):
    # Demo-call failure: "Hi, it's Niamh", heard as "Naim", read as a request for a person.
    service, _, bank, _ = make_service([["ACTION transfer"]], {}, verified=False)
    text, up = await spoken_text(service, hello)
    assert text == "Hello. How can I help you today?"
    assert bank.calls == []


async def test_a_caller_who_asks_for_a_person_is_transferred():
    service, _, bank, _ = make_service(
        [["ACTION transfer"]], {"transfer_to_human": {"status": "queued"}}, verified=False
    )
    await spoken_text(service, "Hi, can I talk to a real person please?")
    assert [call.tool for call in bank.calls] == ["transfer_to_human"]


async def test_the_call_ends_anyway_if_speech_never_finishes():
    service, _, bank, _ = make_service(
        [["ACTION end"]], {"end_call": {"status": "ending"}}, end_timeout_s=0.01
    )
    _, up = await spoken_text(service, "Bye now.", then=(SleepFrame(0.1),))
    assert any(isinstance(frame, EndWorkerFrame) for frame in up)


async def test_each_turn_is_reported_to_the_timeline_and_the_call_page():
    from pipecat.processors.frameworks.rtvi.frames import RTVIServerMessageFrame

    from tellerline.agent.recorder import CallTimeline

    timeline = CallTimeline("call-test")
    service, _, _, _ = make_service(
        [["ACTION balance account=current"]],
        {"get_balance": {"balance_eur": 12.5, "available_eur": 12.5}},
        timeline=timeline,
    )
    down, _ = await run_test(
        service, frames_to_send=[LLMContextFrame(context_with("What's my balance?"))]
    )
    [message] = [f.data for f in down if isinstance(f, RTVIServerMessageFrame)]
    assert message["type"] == "tellerline-turn"
    assert message["route"]["skill"] == "assist"
    assert message["model"]["output"] == "ACTION balance account=current"
    assert message["action"] == {"tool": "get_balance", "arguments": {"account": "current"}}
    assert message["bank"]["outcome"] == "ok"
    assert message["spoken"].startswith("On your current account")
    assert timeline.turns[0]["turn"] == 1


async def test_a_held_reply_is_still_spoken():
    service, _, _, _ = make_service(
        [["ACTION verify customer=45127890"]], {}, verified=False, identity_hold_s=0.05
    )
    text, _ = await spoken_text(service, "My customer number is 45127890.")
    assert text == "Could you tell me your date of birth, please?"


def caller_said(*texts):
    """A context in which the caller said `texts` and heard no reply in between."""
    context = LLMContext()
    for text in texts:
        context.add_message({"role": "user", "content": text})
    return context


PAUSE = "Pause my card ending 7780 for a bit."
CARRIED_ON = "It's somewhere in the house."
FROZEN = {"freeze_card": {"status": "frozen", "reason": "lost"}}


async def test_a_reply_the_caller_never_heard_is_withdrawn():
    # They carried on after a pause and took the turn back before a sentence of the reply was
    # said: the agent answers both parts as one turn, as if it had waited.
    service, brain, _, completions = make_service([["Which card is it?"], ["Grand."]], {})
    frames = [LLMContextFrame(caller_said(PAUSE)), LLMContextFrame(caller_said(PAUSE, CARRIED_ON))]
    await run_test(service, frames_to_send=frames)
    second = completions.requests[1]["messages"]
    assert second[-1] == {"role": "user", "content": f"{PAUSE} {CARRIED_ON}"}
    assert not any(m["content"] == "Which card is it?" for m in second)
    assert [m["content"] for m in brain.history[-2:]] == [f"{PAUSE} {CARRIED_ON}", "Grand."]


async def test_a_reply_the_caller_heard_is_kept():
    service, brain, _, completions = make_service([["Which card is it?"], ["Grand."]], {})
    context = caller_said(PAUSE)
    frames = [
        LLMContextFrame(context),
        LLMContextAssistantTurnFrame(text="Which card is it?", timestamp="now"),
        LLMContextFrame(caller_said(CARRIED_ON)),
    ]
    await run_test(service, frames_to_send=frames)
    second = completions.requests[1]["messages"]
    assert {"role": "assistant", "content": "Which card is it?"} in second
    assert second[-1] == {"role": "user", "content": CARRIED_ON}


async def test_what_an_unheard_reply_did_is_not_done_twice():
    # The card was frozen for the first part; the whole sentence asks for the same, and the bank
    # isn't asked again.
    service, _, bank, _ = make_service(
        [["ACTION freeze card=7780 reason=lost"], ["ACTION freeze card=7780 reason=lost"]], FROZEN
    )
    frames = [LLMContextFrame(caller_said(PAUSE)), LLMContextFrame(caller_said(PAUSE, CARRIED_ON))]
    down, _ = await run_test(service, frames_to_send=frames)
    assert len(bank.calls) == 1
    spoken = "".join(f.text for f in down if isinstance(f, LLMTextFrame))
    assert spoken.count("It's the card ending seven seven eight zero") == 2


async def test_a_different_action_for_the_whole_sentence_still_runs():
    service, _, bank, _ = make_service(
        [["ACTION freeze card=7780 reason=lost"], ["ACTION freeze card=7780 reason=stolen"]],
        FROZEN,
    )
    frames = [
        LLMContextFrame(caller_said(PAUSE)),
        LLMContextFrame(caller_said(PAUSE, "It was stolen.")),
    ]
    await run_test(service, frames_to_send=frames)
    assert [call.arguments["reason"] for call in bank.calls] == ["lost", "stolen"]


async def test_the_bank_waits_while_the_caller_can_be_heard():
    import time

    heard_until = time.monotonic() + 0.15
    service, _, bank, _ = make_service(
        [["ACTION freeze card=7780 reason=lost"]],
        FROZEN,
        hears_caller=lambda: time.monotonic() < heard_until,
    )
    asked_at = []
    run = bank.run

    async def timed_run(action):
        asked_at.append(time.monotonic())
        return await run(action)

    bank.run = timed_run
    await spoken_text(service, PAUSE)
    assert asked_at and asked_at[0] >= heard_until


async def test_a_withdrawn_turn_is_marked_on_the_timeline_and_the_call_page():
    from pipecat.processors.frameworks.rtvi.frames import RTVIServerMessageFrame

    from tellerline.agent.recorder import CallTimeline

    timeline = CallTimeline("call-test")
    service, _, _, _ = make_service([["Which card is it?"], ["Grand."]], {}, timeline=timeline)
    frames = [LLMContextFrame(caller_said(PAUSE)), LLMContextFrame(caller_said(PAUSE, CARRIED_ON))]
    down, _ = await run_test(service, frames_to_send=frames)
    assert timeline.turns[0]["withdrawn"] is True
    assert "withdrawn" not in timeline.turns[1]
    messages = [f.data for f in down if isinstance(f, RTVIServerMessageFrame)]
    assert {"type": "tellerline-withdrawn", "turn": 1} in messages
