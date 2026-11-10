"""The advisor's offline gate runs without a network."""

from finboy.services.advisor import coach, evaluate

from .support import make_settings


def test_the_case_set_is_well_formed_and_answerable() -> None:
    found = evaluate.cases()
    assert evaluate.check(found) == []
    assert {case["language"] for case in found} == set(evaluate.STYLES)
    assert evaluate.main(["--check"]) == 0


def test_an_unknown_guide_or_a_plan_without_its_numbers_is_reported() -> None:
    plan = {"calculation": "emi", "amount_rupees": 100000, "months": 12}
    problems = evaluate.check(
        [
            {
                "id": "guide",
                "language": "en",
                "turns": ["What is PPF?"],
                "expect": {"policy": "answer", "sources": ["no-such-guide"]},
            },
            {
                "id": "plan",
                "language": "en",
                "turns": ["EMI on a 1 lakh loan for 12 months?"],
                "expect": {"policy": "answer", "figures": ["₹8,885"], "plan": plan},
            },
        ]
    )
    assert "guide: no guide no-such-guide" in problems
    assert "plan: plan_numbers refuses it" in problems  # they never gave a rate
    assert "plan: FinBoy cannot give 8885" in problems


def test_a_coach_line_that_breaks_a_template_or_invents_a_figure_is_reported(monkeypatch) -> None:
    monkeypatch.setattr(evaluate.coach, "line", lambda _nudge, _language: "Spent ₹9,999\nthis week")
    problems = evaluate.check_coach()
    assert any("not a template parameter" in item for item in problems)
    assert any("a figure not in its facts" in item for item in problems)
    assert evaluate.main(["--check"]) == 1


def test_the_live_coach_gate_counts_what_the_advisor_worded(monkeypatch, capsys) -> None:
    worded = coach.Worded("₹4,200 of ₹5,000 spent.", "advisor")
    monkeypatch.setattr(evaluate.coach, "compose", lambda *_args, **_kwargs: worded)
    assert evaluate.live_coach(make_settings(), 1) is True
    plain = coach.Worded("₹4,200 of ₹5,000 spent.", "fallback")
    monkeypatch.setattr(evaluate.coach, "compose", lambda *_args, **_kwargs: plain)
    assert evaluate.live_coach(make_settings(), 1) is False
    printed = capsys.readouterr().out
    assert "budget_near/hi: 1 sent as written by code" in printed
    assert "₹" not in printed, "kinds and languages only, never the words"
