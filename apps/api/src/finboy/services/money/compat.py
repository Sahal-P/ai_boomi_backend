"""Keep the current client readable during the backend-first UX rollout."""

from finboy.services.money.engine import CashFlowSimulation


def simulation_response(
    value: CashFlowSimulation, *, include_overdue_line: bool
) -> CashFlowSimulation:
    if include_overdue_line:
        return value
    # Legacy clients have a closed four-label enum. Combine liabilities without
    # changing the calculation; the UX client opts into the explicit split.
    lines = [
        line.model_copy(
            update={
                "amount_minor": value.summary.upcoming_commitments_minor
                + value.summary.overdue_commitments_minor
            }
        )
        if line.label_key == "upcoming_commitments"
        else line
        for line in value.lines
        if line.label_key != "overdue_commitments"
    ]
    return value.model_copy(update={"lines": lines})
