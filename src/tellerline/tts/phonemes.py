"""Split phoneme strings into pieces Kokoro can render in one pass."""

# Kokoro's context holds 510 phoneme tokens plus start and end markers.
MAX_PHONEMES = 510

_BREAKS = (".!?", ";:", ",—", " ")


def split_phonemes(phonemes: str, limit: int = MAX_PHONEMES) -> list[str]:
    """Split at the strongest punctuation (then a space) that keeps each piece within ``limit``."""
    phonemes = phonemes.strip()
    pieces = []
    while len(phonemes) > limit:
        window = phonemes[:limit]
        cut = -1
        for marks in _BREAKS:
            cut = max(window.rfind(mark) for mark in marks)
            if cut > 0:
                break
        cut = cut + 1 if cut > 0 else limit
        pieces.append(phonemes[:cut].strip())
        phonemes = phonemes[cut:].strip()
    if phonemes:
        pieces.append(phonemes)
    return pieces
