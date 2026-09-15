from bench.caller import as_spoken


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
