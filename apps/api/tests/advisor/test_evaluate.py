"""The advisor's offline gate runs without a network."""

from finboy.services.advisor import evaluate


def test_the_case_set_is_well_formed_and_answerable() -> None:
    found = evaluate.cases()
    assert evaluate.check(found) == []
    assert {case["language"] for case in found} == set(evaluate.STYLES)
    assert evaluate.main(["--check"]) == 0
