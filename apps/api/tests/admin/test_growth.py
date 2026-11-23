"""Growth over time (docs/admin-growth/contract.md) from plain inputs, without a database."""

from datetime import UTC, date, datetime, time, timedelta
from uuid import uuid4

from finboy.services.accounts.visits import Funnel
from finboy.services.admin.growth import Member, Span, assemble, funnel_totals, spans, walk
from finboy.services.admin.views import GrowthFunnel

TODAY = date(2026, 11, 24)  # a Tuesday
NO_VISITS = GrowthFunnel(
    opened=0,
    tapped=0,
    signed_up=0,
    agreed=0,
    first_record=0,
    direct_signed_up=0,
    direct_agreed=0,
    direct_first_record=0,
)


def member(joined: date, *, left: date | None = None, minutes: int | None = None) -> Member:
    started = datetime.combine(joined, time(3, 0), UTC)
    return Member(
        id=uuid4(),
        started=started,
        joined=joined,
        left=left,
        first_record=started + timedelta(minutes=minutes) if minutes is not None else None,
    )


def test_periods_end_with_the_running_day_week_or_month() -> None:
    days = spans("day", 30, TODAY)
    assert len(days) == 30
    assert days[0] == Span(date(2026, 10, 26), date(2026, 10, 26))
    assert days[-1] == Span(TODAY, TODAY)

    weeks = spans("week", 12, TODAY)
    assert len(weeks) == 12
    assert weeks[0].start == date(2026, 9, 7)
    assert weeks[-1] == Span(date(2026, 11, 23), date(2026, 11, 29))
    assert {week.start.weekday() for week in weeks} == {0}  # Mondays

    months = spans("month", 12, TODAY)
    assert months[0] == Span(date(2025, 12, 1), date(2025, 12, 31))
    assert Span(date(2026, 2, 1), date(2026, 2, 28)) in months
    assert months[-1] == Span(date(2026, 11, 1), date(2026, 11, 30))
    assert spans("month", 1, date(2028, 2, 10)) == [Span(date(2028, 2, 1), date(2028, 2, 29))]

    # A week across the new year belongs to the Monday that starts it.
    assert walk(date(2026, 12, 30), date(2027, 1, 5), "week") == [
        Span(date(2026, 12, 28), date(2027, 1, 3)),
        Span(date(2027, 1, 4), date(2027, 1, 10)),
    ]


def household_mix() -> tuple[list[Member], dict, list]:
    first = member(date(2026, 11, 2), minutes=30)
    erased = member(date(2026, 11, 9), left=date(2026, 11, 20))
    late = member(date(2026, 11, 17), minutes=90)
    activity = {
        first.id: {date(2026, 11, 2), date(2026, 11, 10)},
        # A message before agreeing doesn't count; the erased household's went with it.
        late.id: {date(2026, 11, 16), date(2026, 11, 18), TODAY},
    }
    saved = [
        (first.id, date(2026, 11, 10), 3),
        (late.id, date(2026, 11, 16), 2),  # before it agreed
        (late.id, TODAY, 1),
    ]
    return [first, erased, late], activity, saved


def test_points_count_who_joined_left_was_here_and_was_active() -> None:
    members, activity, saved = household_mix()
    growth = assemble("12w", TODAY, members, activity, saved, NO_VISITS)
    assert (growth.unit, growth.cohort_unit, growth.today) == ("week", "week", TODAY)
    # The weeks before the first household agreed are left out.
    assert [point.start for point in growth.points] == [
        date(2026, 11, 2),
        date(2026, 11, 9),
        date(2026, 11, 16),
        date(2026, 11, 23),
    ]
    rows = [
        (p.joined, p.left, p.households, p.active, p.records, p.recording, p.partial)
        for p in growth.points
    ]
    assert rows == [
        (1, 0, 1, 1, 0, 0, False),
        (1, 0, 2, 1, 3, 1, False),
        (1, 1, 2, 1, 0, 0, False),  # the erased household left on the 20th
        (0, 0, 2, 1, 1, 1, True),  # the running week, so far
    ]
    summary = growth.summary
    assert (summary.joined, summary.joined_before, summary.left, summary.households) == (3, 0, 1, 2)
    assert summary.active_week == 1
    assert (summary.activated, summary.minutes_to_record) == (2, 60.0)


def test_cohorts_follow_each_joining_week_to_now() -> None:
    members, activity, saved = household_mix()
    cohorts = assemble("12w", TODAY, members, activity, saved, NO_VISITS).cohorts
    assert [(c.start, c.households, c.active) for c in cohorts] == [
        (date(2026, 11, 2), 1, [1, 1, 0, 0]),
        (date(2026, 11, 9), 1, [0, 0, 0]),  # erased: its activity went with it
        (date(2026, 11, 16), 1, [1, 1]),
        (date(2026, 11, 23), 0, [0]),
    ]


def test_thirty_days_group_joiners_by_week_and_a_year_by_month() -> None:
    joined = member(date(2026, 10, 15))
    activity = {joined.id: {date(2026, 10, 15), date(2026, 11, 3)}}
    days = assemble("30d", TODAY, [joined], activity, [], NO_VISITS)
    assert days.cohort_unit == "week"
    assert len(days.points) == 30  # it joined before these 30 days, so none are left out
    assert days.cohorts[0].start == date(2026, 10, 26)  # the Monday on or before the 30 days
    assert days.summary.joined == 0
    assert days.summary.joined_before == 1  # 26 September to 25 October

    months = assemble("12m", TODAY, [joined], activity, [], NO_VISITS)
    assert [(c.start, c.households, c.active) for c in months.cohorts] == [
        (date(2026, 10, 1), 1, [1, 1]),
        (date(2026, 11, 1), 0, [0]),
    ]
    assert [point.start for point in months.points] == [date(2026, 10, 1), date(2026, 11, 1)]


def test_no_households_shows_nothing_but_the_visits() -> None:
    visits = NO_VISITS.model_copy(update={"opened": 12, "tapped": 4})
    growth = assemble("30d", TODAY, [], {}, [], visits)
    assert (growth.points, growth.cohorts) == ([], [])
    assert growth.summary.model_dump() == {
        "joined": 0,
        "joined_before": 0,
        "left": 0,
        "households": 0,
        "active_week": 0,
        "activated": 0,
        "minutes_to_record": None,
    }
    assert growth.funnel.opened == 12


def test_a_first_record_before_sign_up_is_not_a_time() -> None:
    early = member(TODAY, minutes=-5)  # an imported record older than the household
    growth = assemble("30d", TODAY, [early], {}, [], NO_VISITS)
    assert (growth.summary.activated, growth.summary.minutes_to_record) == (1, None)


def test_funnel_totals_keep_sign_ups_without_a_visit_apart() -> None:
    def row(direct: bool, *counts: int) -> Funnel:
        opened, tapped, signed_up, agreed, first_record = counts
        return Funnel(
            source=None if direct else "ig",
            medium=None if direct else "paid_social",
            campaign=None,
            direct=direct,
            opened=opened,
            tapped=tapped,
            signed_up=signed_up,
            agreed=agreed,
            first_record=first_record,
            minutes_to_tap=None,
            minutes_to_sign_up=None,
            minutes_to_record=None,
        )

    totals = funnel_totals(
        [row(False, 300, 40, 12, 10, 6), row(False, 63, 8, 3, 1, 0), row(True, 0, 0, 4, 3, 2)]
    )
    assert totals.model_dump() == {
        "opened": 363,
        "tapped": 48,
        "signed_up": 15,
        "agreed": 11,
        "first_record": 6,
        "direct_signed_up": 4,
        "direct_agreed": 3,
        "direct_first_record": 2,
    }
