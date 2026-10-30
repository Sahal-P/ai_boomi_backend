"""The money check-ups a household asks for on WhatsApp: today, this week, this month, budgets,
the savings goal and the monthly check-in choice (docs/money-manager-round/contract.md).

Figures come from confirmed records through the money engine; no model is called. Only the
budgets, goal and check-in choice the household sets are stored. Advice stays on budgeting and
discipline, never on specific investments.
"""

import re
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from finboy.core.clock import today_ist
from finboy.services.money import budgets
from finboy.services.money.engine import PeriodSpec, money_summary, upcoming_commitments
from finboy.services.whatsapp import prompts

if TYPE_CHECKING:
    from finboy.db.models.whatsapp import WhatsAppPrompt
    from finboy.services.whatsapp.pilot import Conversation
    from finboy.services.whatsapp.statement import Statement

END = r"(?:\s+(?:बताओ|बताइए|बताइये|दिखाओ|दिखाइए|दो|दीजिए|batao|dikhao|പറയൂ|കാണിക്കൂ|തരൂ))?\s*[।.!?]*\s*"
SUMMARY = r"(?:\s+(?:summary|hisab|hisaab|हिसाब|का\s+हिसाब|ka\s+hisab|കണക്ക്))?"
WEEK = re.compile(
    r"\s*(?:(?:मेरा\s+|my\s+|weekly\s+|എന്റെ\s+)?(?:हिसाब|हिसाब-किताब|hisaab|hisab|summary|കണക്ക്)"
    r"|(?:this\s+)?week|weekly|इस\s+हफ़्ते|इस\s+हफ्ते|is\s+hafte|ഈ\s+ആഴ്ച(?:യിലെ)?)" + SUMMARY + END,
    re.IGNORECASE,
)
TODAY = re.compile(
    r"\s*(?:today|today's|aaj|आज|आज\s+का|ഇന്ന്|ഇന്നത്തെ|innu|innathe)" + SUMMARY + END,
    re.IGNORECASE,
)
MONTH = re.compile(
    r"\s*(?:(?:this\s+)?month|monthly|month's|इस\s+महीने|इस\s+महीने\s+का|महीना|is\s+mahine"
    r"|mahina|ഈ\s+മാസം|ഈ\s+മാസത്തെ|budgets?|बजट|ബജറ്റ്|goal|savings|बचत|സമ്പാദ്യം)" + SUMMARY + END,
    re.IGNORECASE,
)


def asked(text: str) -> Callable[[Conversation], str | None] | None:
    """The check-up a whole message asks for, if it is one: "today", "this week", "this month"."""
    for pattern, reply in ((TODAY, today), (WEEK, week), (MONTH, month)):
        if pattern.fullmatch(text):
            return reply
    return None


def _reply(
    conversation: Conversation,
    text: str,
    spoken: str,
    buttons: list[tuple[str, str]] | None = None,
) -> str | None:
    sent = conversation.send(text, buttons)
    if sent:
        conversation.speak(spoken)
    return conversation.done(sent)


def today(conversation: Conversation) -> str | None:
    session, words = conversation.session, conversation.words
    day = today_ist()
    summary = money_summary(
        session,
        user_id=conversation.binding.user_id,
        period=PeriodSpec(kind="range", start_date=day, end_date=day),
    )
    session.rollback()  # release the snapshot lock before any network call
    if not (summary.tracked_income_minor or summary.confirmed_outflows_minor):
        return _reply(conversation, words.TODAY_EMPTY, words.TODAY_EMPTY_SPEECH)
    text, spoken = words.today(
        income=summary.tracked_income_minor,
        outflow=summary.confirmed_outflows_minor,
        count=summary.outflow_transaction_count,
        top=[(item.category, item.amount_minor) for item in summary.categories][:3],
    )
    return _reply(conversation, text, spoken)


def week(conversation: Conversation) -> str | None:
    """The reply to हिसाब: engine figures for Monday to today, plus dues in the next 7 days."""
    session, user_id, words = conversation.session, conversation.binding.user_id, conversation.words
    day = today_ist()
    monday = day - timedelta(days=day.weekday())
    summary = money_summary(
        session, user_id=user_id, period=PeriodSpec(kind="range", start_date=monday, end_date=day)
    )
    ahead = upcoming_commitments(
        session,
        user_id=user_id,
        period=PeriodSpec(kind="range", start_date=day, end_date=day + timedelta(days=7)),
    )
    session.rollback()  # release the snapshot lock before any network call
    top = [(item.category, item.amount_minor) for item in summary.categories if item.amount_minor]
    dues = [(row.amount_minor, row.label, row.due_date) for row in ahead[:3]]
    if not (
        summary.tracked_income_minor
        or summary.confirmed_outflows_minor
        or dues
        or summary.overdue_commitments_minor
        or summary.pending_review_count
    ):
        return _reply(conversation, words.WEEK_EMPTY, words.WEEK_EMPTY_SPEECH)
    text, spoken = words.week(
        income=summary.tracked_income_minor,
        outflow=summary.confirmed_outflows_minor,
        top=top[:3],
        dues=dues,
        overdue=summary.overdue_commitments_minor,
        waiting=summary.pending_review_count,
    )
    return _reply(conversation, text, spoken)


def month(conversation: Conversation) -> str | None:
    """This month so far: in, out, where it went, budgets, the savings goal and bills ahead,
    with the monthly check-in offered (or stopped) when its template is configured."""
    session, binding, words = conversation.session, conversation.binding, conversation.words
    plan = budgets.month_plan(session, binding.user_id)
    ahead = upcoming_commitments(
        session,
        user_id=binding.user_id,
        period=PeriodSpec(kind="range", start_date=plan.as_of, end_date=plan.end),
    )
    dues = [(row.amount_minor, row.label, row.due_date) for row in ahead[:3]]
    if not (plan.income_minor or plan.spent_minor or plan.budgets or plan.goal_minor or dues):
        session.rollback()
        return _reply(conversation, words.MONTH_EMPTY, words.MONTH_EMPTY_SPEECH)
    text, spoken = words.month(
        month=plan.as_of.month,
        income=plan.income_minor,
        outflow=plan.spent_minor,
        saved=plan.saved_minor,
        goal=plan.goal_minor,
        top=plan.top,
        budgets=plan.budgets,
        dues=dues,
        waiting=plan.waiting,
    )
    buttons = None
    if conversation.settings.whatsapp_checkin_template:
        opted_in = binding.checkin_opt_in_at is not None
        offer = prompts.open_prompt(session, binding, "checkin_opt_in")
        buttons = [
            (prompts.button(offer, "nocheckin"), words.CHECKIN_NO)
            if opted_in
            else (prompts.button(offer, "checkin"), words.CHECKIN_YES)
        ]
        if not opted_in:
            text += "\n\n" + words.CHECKIN_ASK
    session.commit()
    return _reply(conversation, text, spoken, buttons)


# The same check-ups for a message d1-ultra recognised as one (statement.Statement.checkup).
CHECKUPS: dict[str, Callable[[Conversation], str | None]] = {
    "today": today,
    "week": week,
    "month": month,
}


def set_budget(conversation: Conversation, reading: Statement) -> str | None:
    """ "food budget 5000": a monthly limit for one category, or for all spending; 0 removes it."""
    session, binding, words = conversation.session, conversation.binding, conversation.words
    category = "total" if reading.overall else reading.category
    try:
        budgets.set_budget(session, binding.user_id, category, reading.amount_minor or None)
    except ValueError:
        session.rollback()
        return conversation.done(conversation.send(words.AMOUNT_UNCLEAR), "amount_unclear")
    status = next(
        (
            item
            for item in budgets.month_plan(session, binding.user_id).budgets
            if item.category == category
        ),
        None,
    )
    session.commit()
    if status is None:
        return _reply(conversation, words.budget_removed(category), words.OK)
    return _reply(conversation, words.budget_set(status), words.BUDGET_SET_SPEECH)


def set_goal(conversation: Conversation, reading: Statement) -> str | None:
    """ "save 5000 a month": the monthly savings goal shown in every month summary."""
    session, binding, words = conversation.session, conversation.binding, conversation.words
    try:
        budgets.set_goal(session, binding.user_id, reading.amount_minor or None)
    except ValueError:
        session.rollback()
        return conversation.done(conversation.send(words.AMOUNT_UNCLEAR), "amount_unclear")
    plan = budgets.month_plan(session, binding.user_id)
    session.commit()
    if plan.goal_minor is None:
        return _reply(conversation, words.GOAL_REMOVED, words.OK)
    text = (
        words.goal_set(plan.goal_minor)
        + "\n"
        + words.goal_line(plan.goal_minor, plan.saved_minor, plan.income_minor)
    )
    return _reply(conversation, text, words.GOAL_SET_SPEECH)


def checkin_choice(conversation: Conversation, prompt: WhatsAppPrompt, choice: str) -> str | None:
    """The monthly check-in is strictly opt-in, and can be stopped the same way."""
    session, binding, words = conversation.session, conversation.binding, conversation.words
    prompts.answer(prompt)
    binding.checkin_opt_in_at = datetime.now(UTC) if choice == "checkin" else None
    session.commit()
    text = words.CHECKIN_ON if choice == "checkin" else words.CHECKIN_OFF
    return _reply(conversation, text, text)
