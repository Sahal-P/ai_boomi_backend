"""One assistant for web and WhatsApp. All financial values come from the money engine."""

from uuid import UUID

from sqlalchemy.orm import Session

from finboy.core.config import Settings
from finboy.core.errors import ProviderUnavailable
from finboy.core.languages import DisplayStyle
from finboy.services.assistant.intent import parse_intent
from finboy.services.assistant.language import normalize_speech, resolve_style
from finboy.services.assistant.models import AskRequest, AssistantAnswer, AssistantFact
from finboy.services.assistant.templates import DISCLAIMER, RECORDS_NOTE, render, speech_disclaimer
from finboy.services.money import engine


def answer_question(
    session: Session, *, user_id: UUID, text: str, display_style: DisplayStyle, settings: Settings
) -> AssistantAnswer:
    request = AskRequest(text=text, display_style=display_style)
    if not request.text.strip():
        raise ValueError("A question is required")
    parsed = parse_intent(request.text, settings)
    style, language = resolve_style(request.text, request.display_style)
    facts: list[AssistantFact] = []
    evidence: list[engine.TransactionView] = []
    simulation: engine.CashFlowSimulation | None = None
    warnings: list[str] = []
    values: dict[str, int] = {}
    policy = "answer"
    key = parsed.intent
    summary: engine.MoneySummary | None = None
    if parsed.intent == "regulated_advice":
        key, policy = "decline", "decline"
    elif parsed.intent == "out_of_scope":
        key, policy = "scope", "decline"
    elif parsed.intent == "clarification":
        key, policy = "clarify", "clarify"
    elif parsed.intent == "education":
        key = parsed.topic or "sip"
    elif parsed.intent in {"affordability_check", "savings_simulation"} and (
        parsed.amount_minor is None or parsed.period.kind != "current_month"
    ):
        key, policy = "clarify", "clarify"
    else:
        try:
            if parsed.intent in {"affordability_check", "savings_simulation"}:
                simulation = engine.simulate_monthly_commitment(
                    session,
                    user_id=user_id,
                    monthly_amount_minor=parsed.amount_minor,
                    label="Proposed monthly commitment",
                )
                summary = simulation.summary
                values = {
                    "income": summary.tracked_income_minor,
                    "outflows": summary.confirmed_outflows_minor,
                    "upcoming": summary.upcoming_commitments_minor,
                    "proposed": simulation.proposed_monthly_minor,
                    "remaining": simulation.remaining_after_proposal_minor,
                }
                facts = [
                    AssistantFact(key=name, amount_minor=amount, currency="INR")
                    for name, amount in values.items()
                ]
                warnings.extend(simulation.warnings)
                key = "simulation"
            else:
                summary = engine.money_summary(session, user_id=user_id, period=parsed.period)
                if parsed.intent == "spending_query" and parsed.category:
                    totals = engine.category_breakdown(
                        session,
                        user_id=user_id,
                        period=parsed.period,
                        category=parsed.category,
                    )
                    total = next((t for t in totals if t.category == parsed.category), None)
                    if total is None:
                        key = "empty"
                    else:
                        key = "category_spending"
                        values["value"] = total.amount_minor
                        facts.append(
                            AssistantFact(
                                key=parsed.category,
                                amount_minor=total.amount_minor,
                                count=total.transaction_count,
                                currency="INR",
                            )
                        )
                elif parsed.intent == "merchant_lookup":
                    pass
                else:
                    field, count = {
                        "spending_query": (
                            "confirmed_outflows_minor",
                            summary.outflow_transaction_count,
                        ),
                        "income_query": ("tracked_income_minor", summary.income_transaction_count),
                        "unallocated_query": ("estimated_unallocated_minor", None),
                        "upcoming_commitments": (
                            "upcoming_commitments_minor",
                            summary.commitment_count,
                        ),
                    }[parsed.intent]
                    amount = getattr(summary, field)
                    values["value"] = amount
                    facts.append(
                        AssistantFact(key=field, amount_minor=amount, count=count, currency="INR")
                    )
            if parsed.intent != "upcoming_commitments":
                evidence = engine.find_transactions(
                    session,
                    user_id=user_id,
                    period=parsed.period,
                    category=parsed.category,
                    merchant=parsed.merchant,
                    status="confirmed",
                    limit=10,
                )
                if parsed.intent == "merchant_lookup":
                    key = "merchant_lookup" if evidence else "empty"
                    facts.extend(
                        AssistantFact(
                            key=f"transaction:{t.id}", amount_minor=t.amount_minor, currency="INR"
                        )
                        for t in evidence
                    )
            # The money engine alone supplies this count; pending amounts never enter the answer.
            facts.append(
                AssistantFact(key="pending_review_count", count=summary.pending_review_count)
            )
            warnings.append("incomplete_coverage")
            if summary.pending_review_count:
                warnings.append("pending_review_items")
        except NotImplementedError:
            raise ProviderUnavailable("assistant_unavailable") from None
    display = render(key, style, language, values=values, category=parsed.category)
    speech = render(key, style, language, values=values, category=parsed.category, speech=True)
    if summary is not None:
        # Give the actual engine period, avoiding assumptions about the current real date.
        display += f" ({summary.period_start.isoformat()} – {summary.period_end.isoformat()})"
        if summary.pending_review_count:
            display += " " + render("pending", style, language, count=summary.pending_review_count)
            speech += " " + render(
                "pending", style, language, count=summary.pending_review_count, speech=True
            )
        display += " " + render("coverage", style, language)
        if style != "en":
            display += " " + RECORDS_NOTE
        speech += " " + render("coverage", style, language, speech=True)
    if simulation is not None:
        display += " " + DISCLAIMER
        speech += " " + speech_disclaimer(language)
    return AssistantAnswer(
        intent=parsed.intent,
        policy=policy,
        display_text=display,
        speech_text=normalize_speech(speech, language),
        speech_language=language,
        facts=facts,
        simulation=simulation,
        evidence_transactions=evidence,
        warnings=list(dict.fromkeys(warnings)),
    )
