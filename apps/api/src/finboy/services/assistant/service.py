"""One assistant for web and WhatsApp. All financial values come from the money engine."""

from uuid import UUID

from sqlalchemy.orm import Session

from finboy.core.config import Settings
from finboy.core.errors import ProviderUnavailable
from finboy.core.languages import DisplayStyle
from finboy.services.assistant.facts import financial_facts
from finboy.services.assistant.intent import parse_intent
from finboy.services.assistant.labels import local_label, warning_labels
from finboy.services.assistant.language import normalize_speech, resolve_style
from finboy.services.assistant.models import (
    AskRequest,
    AssistantAnswer,
    AssistantFact,
    ResolvedPeriod,
)
from finboy.services.assistant.templates import DISCLAIMER, render, speech_disclaimer
from finboy.services.money import engine
from finboy.services.ux.state import data_version


def answer_question(
    session: Session, *, user_id: UUID, text: str, display_style: DisplayStyle, settings: Settings
) -> AssistantAnswer:
    request = AskRequest(text=text, display_style=display_style)
    if not request.text.strip():
        raise ValueError("A question is required")
    style, language = resolve_style(request.text, request.display_style)
    parsed = parse_intent(request.text, settings, display_style=style, speech_language=language)
    evidence_total = 0
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
    elif parsed.intent == "purchase_planning":
        key, policy = "clarify", "clarify"
    elif parsed.intent == "clarification":
        key, policy = (
            "clarify_period"
            if parsed.clarification_reason == "period"
            else "clarify_merchant"
            if parsed.clarification_reason == "merchant"
            else "clarify",
            "clarify",
        )
    elif parsed.intent == "education":
        if parsed.topic is None:
            key, policy = "clarify", "clarify"
        else:
            key = parsed.topic
    elif parsed.intent in {"affordability_check", "savings_simulation"} and (
        parsed.amount_minor is None or parsed.period.kind != "current_month"
    ):
        key, policy = (
            "clarify_amount" if parsed.amount_minor is None else "clarify_simulation_period",
            "clarify",
        )
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
                    "upcoming": summary.unresolved_commitments_minor,
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
                full = financial_facts(
                    session,
                    user_id=user_id,
                    period=parsed.period,
                    intent=parsed.intent,
                    category=parsed.category,
                    merchant=parsed.merchant,
                )
                evidence, evidence_total = (
                    ([], 0)
                    if parsed.intent == "upcoming_commitments"
                    else (full.evidence, full.total)
                )
                if parsed.intent == "merchant_lookup":
                    key = "merchant_total"
                    values = {
                        "gross": full.gross_minor,
                        "refunds": full.refunds_minor,
                        "value": full.net_minor,
                    }
                    facts = [
                        AssistantFact(key=name, amount_minor=amount, currency="INR")
                        for name, amount in [
                            ("gross_spending", full.gross_minor),
                            ("refunds", full.refunds_minor),
                            ("net_spending", full.net_minor),
                        ]
                    ]
                elif parsed.intent == "spending_query" and parsed.category:
                    key = "category_spending"
                    values["value"] = full.net_minor
                    facts.append(
                        AssistantFact(
                            key=parsed.category,
                            amount_minor=full.net_minor,
                            count=full.total,
                            currency="INR",
                        )
                    )
                else:
                    field, count = {
                        "spending_query": (
                            "confirmed_outflows_minor",
                            summary.outflow_transaction_count,
                        ),
                        "income_query": ("tracked_income_minor", summary.income_transaction_count),
                        "unallocated_query": ("estimated_unallocated_minor", None),
                        "upcoming_commitments": (
                            "unresolved_commitments_minor",
                            summary.commitment_count,
                        ),
                    }[parsed.intent]
                    amount = getattr(summary, field)
                    values["value"] = amount
                    facts.append(
                        AssistantFact(key=field, amount_minor=amount, count=count, currency="INR")
                    )
            if parsed.intent in {"affordability_check", "savings_simulation"}:
                full = financial_facts(
                    session, user_id=user_id, period=parsed.period, intent="unallocated_query"
                )
                evidence, evidence_total = (
                    ([], 0)
                    if parsed.intent == "upcoming_commitments"
                    else (full.evidence, full.total)
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
        speech += " " + render("coverage", style, language, speech=True)
    if simulation is not None:
        display += " " + (
            speech_disclaimer(language)
            if style in {"hi", "ml"}
            else {
                "hinglish": "Yeh tracked cash flow model hai; security kharidne ki salah nahi.",
                "manglish": "Tracked panamozhukku model; nikshepam vangaanulla nirdesham alla.",
            }.get(style, DISCLAIMER)
        )
        speech += " " + speech_disclaimer(language)
    if parsed.reply is not None and policy != "decline":
        if summary is None:
            display, speech = parsed.reply.display_text, parsed.reply.speech_text
        else:
            # AI supplies context only. Engine-backed figures and warnings stay verbatim.
            display = parsed.reply.display_text + "\n\n" + display
            combined = normalize_speech(parsed.reply.speech_text + " " + speech, language)
            if len(combined) <= settings.speech_max_text_characters:
                speech = combined
    for fact in facts:
        fact.label = local_label(fact.key, style)
    return AssistantAnswer(
        data_version=summary.data_version if summary else data_version(session, user_id),
        resolved_period=ResolvedPeriod(
            start=summary.period_start,
            end=summary.period_end,
            label=f"{summary.period_start.isoformat()} – {summary.period_end.isoformat()}",
        )
        if summary
        else None,
        display_language="hi"
        if style in {"hi", "hinglish"}
        else "ml"
        if style in {"ml", "manglish"}
        else "en",
        display_script="Deva" if style == "hi" else "Mlym" if style == "ml" else "Latn",
        evidence_total=evidence_total,
        evidence_sampled=evidence_total > len(evidence),
        warning_labels=warning_labels(warnings, style),
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
