import pytest

from bench.common import has_clause_end, has_sentence_end, percentile, summarize


def test_percentile_matches_linear_interpolation():
    values = [10.0, 20.0, 30.0, 40.0]
    assert percentile(values, 0) == 10.0
    assert percentile(values, 50) == 25.0
    assert percentile(values, 90) == pytest.approx(37.0)
    assert percentile(values, 100) == 40.0


def test_percentile_ignores_input_order():
    assert percentile([3.0, 1.0, 2.0], 50) == 2.0


def test_percentile_rejects_empty_and_out_of_range():
    with pytest.raises(ValueError):
        percentile([], 50)
    with pytest.raises(ValueError):
        percentile([1.0], 101)


def test_summarize_reports_tail_percentiles():
    stats = summarize([float(v) for v in range(1, 101)])
    assert stats["n"] == 100
    assert stats["p50"] == pytest.approx(50.5)
    assert stats["p90"] == pytest.approx(90.1)
    assert summarize([]) == {"n": 0}


def test_sentence_end_needs_following_whitespace():
    assert not has_sentence_end("Your balance is €49.")
    assert not has_sentence_end("Your balance is €49.99")
    assert has_sentence_end("Your card is frozen. Anything")
    assert has_sentence_end("Is that right? ")


def test_final_text_counts_as_a_sentence():
    assert has_sentence_end("Your card is frozen", final=True)
    assert not has_sentence_end("   ", final=True)


def test_clause_end_includes_commas():
    assert has_clause_end("Thanks, Aoife")
    assert not has_sentence_end("Thanks, Aoife")
