from datetime import date

import pytest

from tellerline.understanding import (
    annotate_dates,
    normalise_digits,
    normalise_money,
    spoken_year,
    understand,
    words_to_number,
)

MONDAY = date(2026, 9, 14)


@pytest.mark.parametrize(
    ("said", "written"),
    [
        ("It ends in seven two oh six.", "It ends in 7206."),
        (
            "Block the card ending double oh four one, please.",
            "Block the card ending 0041, please.",
        ),
        ("It's double seven four five double one oh two.", "It's 77451102."),
        ("treble three one", "3331"),
        ("It's 5 8 3 3 1 0 2 6.", "It's 58331026."),
        ("It's 6 2 0 4, 1 9 5 8, and", "It's 62041958, and"),
        ("My customer number is 3011 8842.", "My customer number is 30118842."),
        # Read in groups with pauses that speech recognition wrote as full stops.
        ("It's four five one two. seven eight nine zero.", "It's 45127890."),
        ("It's 573. zero two nine one eight.", "It's 57302918."),
        ("Born 14-07-1985", "Born 14-07-1985"),
        ("It ends in 4217. Three days ago", "It ends in 4217. Three days ago"),
        # Left alone: a full card number, single number words, ordinary lists of numbers.
        ("It's 4921 5561 0093 4217.", "It's 4921 5561 0093 4217."),
        (
            "The one ending 4217, the last four please.",
            "The one ending 4217, the last four please.",
        ),
        ("Oh, and the number's 22904718.", "Oh, and the number's 22904718."),
        ("Yes, 12, 13", "Yes, 12, 13"),
    ],
)
def test_digits(said, written):
    assert normalise_digits(said) == written


@pytest.mark.parametrize(
    ("said", "written"),
    [
        ("It was 34 euro 60.", "It was €34.60."),
        ("9 euro and 99 cent", "€9.99"),
        ("forty-five euro", "€45"),
        ("a hundred and twenty euro", "€120"),
        ("twelve euro ninety-nine", "€12.99"),
        ("a 120 euro charge", "a €120 charge"),
        ("200 euro a month", "€200 a month"),
        ("7.50 euro", "€7.50"),
        ("and fifteen euro", "and €15"),
        # Demo call: a pause after "euro" written as a full stop, "cent" heard as "sent".
        ("It was 34 euro. And 60 sent last Tuesday.", "It was €34.60 last Tuesday."),
        ("34 euro, and sixty cent", "€34.60"),
        ("I sent 20 euro to my sister", "I sent €20 to my sister"),
        ("49.99 by StreamFlix", "49.99 by StreamFlix"),
    ],
)
def test_money(said, written):
    assert normalise_money(said) == written


@pytest.mark.parametrize(
    ("said", "written"),
    [
        ("yesterday", "yesterday (2026-09-13)"),
        ("the day before yesterday", "the day before yesterday (2026-09-12)"),
        ("last Tuesday", "last Tuesday (2026-09-08)"),
        ("on Saturday", "on Saturday (2026-09-12)"),
        # Today is a Monday: "Monday" means last week's.
        ("on Monday", "on Monday (2026-09-07)"),
        ("three days ago", "three days ago (2026-09-11)"),
        ("on the 3rd, but", "on the 3rd (2026-09-03), but"),
        ("on the 20th", "on the 20th (2026-08-20)"),  # still to come this month: last month
        ("charged on the 12th.", "charged on the 12th (2026-09-12)."),
        ("the 2nd card", "the 2nd card"),
        ("on the 10th of September.", "on the 10th of September (2026-09-10)."),
        ("the 25th of December", "the 25th of December (2025-12-25)"),  # not yet this year
        ("born the 21st of November 1978", "born the 21st of November 1978 (1978-11-21)"),
        ("the ninth of June 1964", "the ninth of June 1964 (1964-06-09)"),
        ("the twenty-first of May", "the twenty-first of May (2026-05-21)"),
        ("14/07/1985", "14/07/1985 (1985-07-14)"),
        ("12.08.83", "12.08.83 (1983-08-12)"),
        ("March 3rd 1991", "March 3rd 1991 (1991-03-03)"),
        (
            "the third of March nineteen ninety-one",
            "the third of March nineteen ninety-one (1991-03-03)",
        ),
        (
            "the second of January two thousand and one",
            "the second of January two thousand and one (2001-01-02)",
        ),
        ("the 31st of February 1990", "the 31st of February 1990"),  # not a date
    ],
)
def test_dates(said, written):
    assert annotate_dates(said, MONDAY) == written


def test_number_words():
    assert words_to_number("forty-five") == 45
    assert words_to_number("one hundred and twenty") == 120
    assert words_to_number("two thousand and five") == 2005
    assert words_to_number("banana") is None
    assert spoken_year("nineteen ninety-one") == 1991
    assert spoken_year("twenty twenty-five") == 2025
    assert spoken_year("two thousand") == 2000


def test_understand_combines_every_step():
    said = "Corrib Taxis took 34 euro 60 off me yesterday, card ending four two one seven."
    assert understand(said, MONDAY) == (
        "Corrib Taxis took €34.60 off me yesterday (2026-09-13), card ending 4217."
    )


def test_understanding_is_idempotent():
    said = "It was 12 euro 99 on the 3rd, the day before yesterday, ending double oh four one."
    once = understand(said, MONDAY)
    assert understand(once, MONDAY) == once


def test_american_style_years_and_a_pause_before_the_year():
    said = "Born the second of May. nineteen hundred eighty seven."
    assert annotate_dates(said, MONDAY).endswith("nineteen hundred eighty seven (1987-05-02).")
    assert spoken_year("nineteen hundred and five") == 1905
