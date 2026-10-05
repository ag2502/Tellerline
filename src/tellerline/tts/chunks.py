"""Split what the agent says into clauses, so Kokoro can start talking sooner.

Kokoro renders a whole piece of text before any of it can play, and the time grows with the
text: on the MacBook Air M5 about 0.1 s for a short clause, 0.3 s for a full balance sentence,
and 1.2 s for five transactions read out as one sentence. Speaking clause by clause means only
the first clause stands between the caller and the reply; later clauses render while the first
one plays, since Kokoro runs roughly fifteen times faster than real time.

Kokoro's own silence at the edges of each render is trimmed (``tellerline.tts.kokoro_mlx``), so
the pause a listener expects at a comma or between sentences is put back as silence.

Each sentence is chunked on its own, so the same sentence always yields the same chunks whether
it arrives alone (a streamed reply, which Pipecat hands over sentence by sentence) or with
others (the greeting); rendered chunks can then be cached by their text.
"""

import re
from dataclasses import dataclass

# Silence after a clause, by the punctuation that ends it.
CLAUSE_PAUSES_S = {",": 0.12, ";": 0.2, ":": 0.2, "—": 0.2}
# Silence between two sentences of one reply.
SENTENCE_PAUSE_S = 0.25
# Later clauses of a sentence are merged up to this length: fewer seams, and each render still
# finishes well before the audio queued ahead of it has played.
MAX_CHUNK_CHARS = 140
# A first clause of fewer words is merged with the next, so a sentence doesn't open on a lone
# "So," followed by a pause.
MIN_FIRST_WORDS = 2

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")
_CLAUSE_END = re.compile(r"(?<=[,;:—])\s+")


@dataclass(frozen=True)
class Chunk:
    text: str
    pause_s: float = 0.0  # silence to add after this chunk


def sentences(text: str) -> list[str]:
    return [s for s in _SENTENCE_END.split(text.strip()) if s]


def _sentence_pieces(sentence: str, max_chars: int) -> list[str]:
    clauses = [c for c in _CLAUSE_END.split(sentence) if c]
    first = clauses.pop(0)
    while clauses and len(first.split()) < MIN_FIRST_WORDS:
        first = f"{first} {clauses.pop(0)}"
    pieces = [first]
    for clause in clauses:
        if len(pieces) > 1 and len(pieces[-1]) + 1 + len(clause) <= max_chars:
            pieces[-1] = f"{pieces[-1]} {clause}"
        else:
            pieces.append(clause)
    return pieces


def speech_chunks(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[Chunk]:
    """The pieces to render one at a time, each with the silence that follows it.

    Within a sentence the first clause stands alone and the rest are merged:
    "On your current account, the balance is twelve euro." becomes "On your current account,"
    then "the balance is twelve euro.", with a comma's pause between them.
    """
    chunks: list[Chunk] = []
    for sentence in sentences(text):
        if chunks:
            chunks[-1] = Chunk(chunks[-1].text, SENTENCE_PAUSE_S)
        pieces = _sentence_pieces(sentence, max_chars)
        for piece in pieces[:-1]:
            chunks.append(Chunk(piece, CLAUSE_PAUSES_S.get(piece[-1], 0.0)))
        chunks.append(Chunk(pieces[-1]))
    return chunks
