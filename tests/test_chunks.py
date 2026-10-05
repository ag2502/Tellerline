from tellerline.actions import common_questions
from tellerline.banking.responses import FIXED_PHRASES
from tellerline.tts.chunks import (
    CLAUSE_PAUSES_S,
    MAX_CHUNK_CHARS,
    SENTENCE_PAUSE_S,
    Chunk,
    speech_chunks,
)


def texts(text: str) -> list[str]:
    return [chunk.text for chunk in speech_chunks(text)]


def test_the_first_clause_is_spoken_on_its_own():
    chunks = speech_chunks(
        "On your current account, the balance is one thousand, two hundred and fifty euro."
    )
    assert chunks == [
        Chunk("On your current account,", CLAUSE_PAUSES_S[","]),
        Chunk("the balance is one thousand, two hundred and fifty euro."),
    ]


def test_a_one_word_opening_joins_the_next_clause():
    assert texts("Thanks, Aoife, you're verified.") == ["Thanks, Aoife,", "you're verified."]


def test_a_sentence_without_clauses_stays_whole():
    assert speech_chunks("What are the last four digits of the card?") == [
        Chunk("What are the last four digits of the card?")
    ]


def test_sentences_are_chunked_separately_with_a_pause_between():
    chunks = speech_chunks("I've frozen that card for you. Would you like a replacement?")
    assert chunks == [
        Chunk("I've frozen that card for you.", SENTENCE_PAUSE_S),
        Chunk("Would you like a replacement?"),
    ]


def test_chunks_match_whether_sentences_arrive_together_or_alone():
    reply = "Hello, you're through to the bank. How can I help you today?"
    together = texts(reply)
    alone = texts("Hello, you're through to the bank.") + texts("How can I help you today?")
    assert together == alone


def test_later_clauses_merge_up_to_the_limit():
    items = ", ".join(f"item number {n} on the list" for n in range(12))
    chunks = speech_chunks(f"Here it is, {items}.")
    assert chunks[0].text == "Here it is,"
    assert all(len(chunk.text) <= MAX_CHUNK_CHARS for chunk in chunks[1:])
    assert " ".join(chunk.text for chunk in chunks) == f"Here it is, {items}."


def test_empty_text_has_no_chunks():
    assert speech_chunks("   ") == []


def test_every_fixed_phrase_opens_quickly():
    """Fixed openings are what the caller hears first, so each must be a short first chunk."""
    for phrase in FIXED_PHRASES:
        assert len(speech_chunks(phrase)[0].text) <= 60, phrase


def test_common_questions_cover_every_missing_value():
    questions = common_questions()
    assert "What are the last four digits of the card?" in questions
    assert "Is that your current account or your savings account?" in questions
    assert (
        "Could you tell me your eight-digit customer number and your date of birth, please?"
        in questions
    )
    assert len(questions) == len(set(questions))
