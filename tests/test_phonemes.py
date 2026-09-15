from tellerline.tts.phonemes import split_phonemes


def test_short_input_is_one_piece():
    assert split_phonemes("jɔː kɑːd ɪz fɹəʊzən.") == ["jɔː kɑːd ɪz fɹəʊzən."]


def test_empty_input_has_no_pieces():
    assert split_phonemes("   ") == []


def test_prefers_sentence_end_over_comma_and_space():
    text = "aaaa, bbbb. cccc dddd"
    assert split_phonemes(text, limit=15) == ["aaaa, bbbb.", "cccc dddd"]


def test_falls_back_to_comma_then_space():
    assert split_phonemes("aaaa, bbbb cccc", limit=12) == ["aaaa,", "bbbb cccc"]
    assert split_phonemes("aaaa bbbb cccc", limit=10) == ["aaaa bbbb", "cccc"]


def test_hard_cut_when_there_is_no_break():
    assert split_phonemes("abcdefghij", limit=4) == ["abcd", "efgh", "ij"]


def test_every_piece_fits_the_limit():
    text = ("həˈləʊ, ðɪs ɪz ə lɒŋ ˈsɛntəns. " * 40).strip()
    pieces = split_phonemes(text)
    assert all(len(piece) <= 510 for piece in pieces)
    assert "".join(pieces).replace(" ", "") == text.replace(" ", "")
