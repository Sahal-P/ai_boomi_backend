"""What the web app is told about a household's plan (docs/subscription-round/contract.md)."""

from datetime import UTC, date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.orm import Session

from finboy.core.config import Settings
from finboy.services.billing import contact, plans
from finboy.services.billing.payu import CHECKOUT_URLS


class ContactView(BaseModel):
    # Masked: "s•••@example.in", "•••• 4821".
    email: str | None
    phone: str | None
    phone_from_whatsapp: bool


class PlanView(BaseModel):
    state: Literal["included", "trial", "active", "grace", "free"]
    premium: bool
    trial_ends_at: datetime | None
    paid_through: datetime | None
    renewal: Literal["manual", "autopay", "off"] | None
    next_charge_on: date | None
    grace_until: datetime | None
    price_minor: int
    can_pay: bool
    autopay_available: bool
    # PayU's checkout origin, so the web app can warm the connection before Pay is tapped.
    checkout_origin: Literal["https://test.payu.in", "https://secure.payu.in"]
    contact: ContactView


def plan_view(
    session: Session, settings: Settings, user_id: UUID, now: datetime | None = None
) -> PlanView | None:
    """None while billing is off: then every household has every feature and no plan UI shows."""
    if not settings.billing_enabled:
        return None
    now = now or datetime.now(UTC)
    plan = plans.plan_for(session, settings, user_id, now)
    known = (
        contact.stored(session, settings, user_id)
        if plan.state != "included"
        else contact.Contact(None, None)
    )
    return PlanView(
        state=plan.state,
        premium=plan.premium,
        trial_ends_at=plan.trial_ends_at,
        paid_through=plan.paid_through,
        renewal=plan.renewal,
        next_charge_on=plan.next_charge_on,
        grace_until=plan.grace_until,
        price_minor=plans.PRICE_MINOR,
        can_pay=plan.can_pay(now),
        autopay_available=settings.payu_autopay_enabled,
        checkout_origin=CHECKOUT_URLS[settings.payu_environment].removesuffix("/_payment"),  # type: ignore[arg-type]
        contact=ContactView(
            email=known.masked_email,
            phone=known.masked_phone,
            phone_from_whatsapp=known.phone_from_whatsapp,
        ),
    )
