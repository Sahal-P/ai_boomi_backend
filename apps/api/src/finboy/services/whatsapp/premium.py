"""FinBoy Premium on WhatsApp (docs/subscription-round/contract.md).

On the Free plan, a voice note, a photo or screenshot, a statement PDF or an AI question gets a
short reply in the person's language with their own pay link; nothing is downloaded, transcribed
or metered first. Typed entries and check-ups stay free. Inside the 24-hour window, one line
follows a reply as the trial ends — once per stage, in the reply's follow-up slot that a due
reminder may already have taken (then it waits for the next message).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from finboy.core.clock import IST
from finboy.db.models.billing import BillingProfile
from finboy.db.models.core import User
from finboy.services.billing import links, plans

if TYPE_CHECKING:
    from finboy.services.whatsapp.pilot import Conversation

# The message kinds that need Premium, and the reply each gets on the Free plan.
REPLIES = {"audio": "PREMIUM_VOICE", "image": "PREMIUM_PHOTO", "document": "PREMIUM_STATEMENT"}


def allowed(conversation: Conversation) -> bool:
    """Pilot households and the owner always are; self-serve households while on Premium."""
    if not conversation.self_serve:
        return True
    return plans.plan_for(
        conversation.session, conversation.settings, conversation.binding.user_id
    ).premium


def pay_link(conversation: Conversation) -> str:
    user_id = conversation.binding.user_id
    epoch = conversation.session.get(User, user_id).session_epoch  # type: ignore[union-attr]
    return links.link(conversation.settings, user_id, epoch, conversation.language)


def refuse(conversation: Conversation, reply: str) -> str | None:
    """The Free plan's answer to a Premium feature; the receipt records `premium_required`."""
    text = getattr(conversation.words, reply).format(link=pay_link(conversation))
    return conversation.done(conversation.send(text), "premium_required")


def days_left(plan: plans.Plan, now: datetime) -> int:
    """Calendar days in India until the trial's last day; 0 on that day."""
    if plan.trial_ends_at is None:
        return 0
    return (plan.trial_ends_at.astimezone(IST).date() - now.astimezone(IST).date()).days


def stage(plan: plans.Plan, now: datetime) -> str | None:
    """Which trial nudge is due: 3 days left, the last day, or just ended (then never again)."""
    if plan.state == "grace":
        return "renewal_failed"
    if plan.trial_ends_at is None or plan.paid_through is not None:
        return None
    left = days_left(plan, now)
    if plan.state == "free":
        return "trial_over" if left >= -7 else None
    if left <= 0:
        return "trial_last"
    return "trial_3d" if left <= 3 else None


def nudge(conversation: Conversation) -> None:
    """After a reply: the trial-ending line, if one is due and not yet sent for this stage."""
    if not conversation.self_serve or not conversation.settings.billing_enabled:
        return
    session, user_id = conversation.session, conversation.binding.user_id
    session.rollback()
    now = datetime.now(UTC)
    plan = plans.plan_for(session, conversation.settings, user_id, now)
    due = stage(plan, now)
    profile = session.get(BillingProfile, user_id)
    if due is None or (profile is not None and profile.last_nudge == due):
        session.rollback()
        return
    words, link = conversation.words, pay_link(conversation)
    text = {
        "trial_3d": words.TRIAL_ENDING.format(days=max(days_left(plan, now), 1), link=link),
        "trial_last": words.TRIAL_LAST_DAY.format(link=link),
        "trial_over": words.TRIAL_OVER.format(link=link),
        "renewal_failed": words.RENEWAL_FAILED.format(link=link),
    }[due]
    session.commit()
    sent = conversation.reply(
        session,
        conversation.config,
        conversation.client,
        conversation.receipt,
        conversation.question,
        text=text,
        reminder=True,
    )
    if not sent:
        return
    profile = session.get(BillingProfile, user_id, with_for_update=True)
    if profile is None:
        profile = BillingProfile(user_id=user_id)
        session.add(profile)
    profile.last_nudge = due
    session.commit()
