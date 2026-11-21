"""The name a household gives on the web (docs/names-search-round/contract.md)."""

import pytest
from finboy.services.accounts.households import clean_name


@pytest.mark.parametrize(
    ("typed", "kept"),
    [
        ("  Asha   Menon ", "Asha Menon"),
        ("अनीता", "अनीता"),
        ("ജോസഫ് കെ.", "ജോസഫ് കെ."),
        ("D'Souza-Pereira", "D'Souza-Pereira"),
        ("A" * 60, "A" * 60),
    ],
)
def test_a_name_in_any_script_is_kept_with_its_spaces_tidied(typed: str, kept: str) -> None:
    assert clean_name(typed) == kept


@pytest.mark.parametrize("typed", ["", "   ", "1234", "!!!", "A" * 61, "Asha​\u0007"])
def test_anything_that_is_not_a_name_is_refused(typed: str) -> None:
    assert clean_name(typed) is None
