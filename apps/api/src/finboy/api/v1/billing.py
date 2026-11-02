"""FinBoy Premium: checkout, receipts, history, AutoPay, pay links and PayU's callbacks.

docs/subscription-round/contract.md. PayU posts its results to /payu/*, which are public and exempt
from the Origin rule: PayU's SHA-512 hash, our txnid and the stored amount decide what counts. The
browser is only ever redirected to the web app, with FinBoy's own payment ID and nothing of PayU's.
"""

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from urllib.parse import parse_qsl
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException

from finboy.api.deps import DB, CurrentUser
from finboy.core.config import Settings
from finboy.core.errors import error_response
from finboy.core.languages import Language
from finboy.db.models.billing import BillingPayment
from finboy.services.billing import checkout, contact, links, mandates
from finboy.services.billing.payu import PAYU_ID, PayUClient, PayUUnavailable
from finboy.services.billing.views import ContactView, PlanView, plan_view

logger = logging.getLogger(__name__)
router = APIRouter(tags=["billing"])

MAX_PAYU_BODY = 16 * 1024
# A pending payment is asked about at most this often while its page is polling.
RECHECK = timedelta(seconds=10)


class ContactInput(BaseModel):
    email: str | None = Field(default=None, max_length=80)
    phone: str | None = Field(default=None, max_length=24)


class LinkInput(BaseModel):
    token: str = Field(min_length=20, max_length=512)


class LinkCheckoutInput(ContactInput, LinkInput):
    pass


class CheckoutView(BaseModel):
    payment_id: UUID
    action: str
    fields: dict[str, str]


class ReceiptInput(BaseModel):
    payment_id: UUID


class ReceiptView(BaseModel):
    status: Literal["started", "scheduled", "pending", "paid", "failed", "abandoned"]
    covers_to: datetime | None
    autopay: bool


class PaymentView(BaseModel):
    id: UUID
    kind: Literal["checkout", "renewal"]
    status: Literal["pending", "paid", "failed"]
    amount_minor: int
    mode: str | None
    autopay: bool
    covers_from: datetime | None
    covers_to: datetime | None
    created_at: datetime


class PaymentsView(BaseModel):
    payments: list[PaymentView]


class LinkView(BaseModel):
    language: Language
    plan: PlanView
    # FinBoy's public WhatsApp number, for "Back to WhatsApp".
    whatsapp_number: str | None


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _plan(session: Session, settings: Settings, user_id: UUID) -> PlanView:
    view = plan_view(session, settings, user_id)
    if view is None:
        raise HTTPException(404)
    return view


@router.post("/billing/checkout")
def start_checkout(
    body: ContactInput, request: Request, session: DB, user_id: CurrentUser
) -> CheckoutView:
    started = checkout.start(
        session, _settings(request), user_id, email=body.email, phone=body.phone, via="web"
    )
    return CheckoutView(payment_id=started.payment_id, action=started.action, fields=started.fields)


@router.post("/billing/receipt")
def receipt(body: ReceiptInput, request: Request, session: DB) -> ReceiptView:
    """One payment's outcome by its unguessable ID; a pending one is re-checked with PayU."""
    settings = _settings(request)
    payment = session.get(BillingPayment, body.payment_id)
    if payment is None or payment.kind != "checkout":
        raise HTTPException(404)
    now = datetime.now(UTC)
    open_ = settings.billing_enabled and payment.status in {"started", "pending"}
    if open_ and now - payment.updated_at > RECHECK:
        txnid, payment_id = payment.txnid, payment.id
        session.execute(
            update(BillingPayment).where(BillingPayment.id == payment_id).values(updated_at=now)
        )
        session.commit()
        try:
            with PayUClient(settings) as client:
                checkout.reconcile(session, settings, client, [txnid], now=now)
        except PayUUnavailable:
            session.rollback()
        payment = session.get(BillingPayment, payment_id) or payment
    return ReceiptView(
        status=payment.status,  # type: ignore[arg-type]
        covers_to=payment.covers_to,
        autopay=payment.mandate_registered,
    )


@router.get("/billing/payments")
def payments(session: DB, user_id: CurrentUser) -> PaymentsView:
    rows = session.scalars(
        select(BillingPayment)
        .where(
            BillingPayment.user_id == user_id,
            BillingPayment.status.in_(("pending", "paid", "failed")),
        )
        .order_by(BillingPayment.created_at.desc())
        .limit(24)
    ).all()
    return PaymentsView(
        payments=[
            PaymentView(
                id=row.id,
                kind=row.kind,  # type: ignore[arg-type]
                status=row.status,  # type: ignore[arg-type]
                amount_minor=row.amount_minor,
                mode=row.mode,
                autopay=row.mandate_registered or row.kind == "renewal",
                covers_from=row.covers_from,
                covers_to=row.covers_to,
                created_at=row.created_at,
            )
            for row in rows
        ]
    )


@router.patch("/billing/contact")
def update_contact(
    body: ContactInput, request: Request, session: DB, user_id: CurrentUser
) -> ContactView:
    settings = _settings(request)
    contact.save(session, settings, user_id, email=body.email, phone=body.phone)
    session.commit()
    return _plan(session, settings, user_id).contact


@router.post("/billing/autopay/cancel")
def cancel_autopay(request: Request, session: DB, user_id: CurrentUser) -> PlanView:
    settings = _settings(request)
    mandates.turn_off(session, settings, user_id)
    return _plan(session, settings, user_id)


@router.post("/billing/link")
def link_view(body: LinkInput, request: Request, session: DB) -> LinkView:
    settings = _settings(request)
    holder = links.read(session, settings, body.token)
    return LinkView(
        language=holder.language,
        plan=_plan(session, settings, holder.user_id),
        whatsapp_number=settings.whatsapp_public_number,
    )


@router.post("/billing/link/checkout")
def link_checkout(body: LinkCheckoutInput, request: Request, session: DB) -> CheckoutView:
    settings = _settings(request)
    holder = links.read(session, settings, body.token)
    started = checkout.start(
        session,
        settings,
        holder.user_id,
        email=body.email,
        phone=body.phone,
        via="link",
        hindi=holder.language == "hi",
    )
    return CheckoutView(payment_id=started.payment_id, action=started.action, fields=started.fields)


async def _body(request: Request) -> bytes:
    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > MAX_PAYU_BODY:
            raise HTTPException(413)
    return bytes(body)


async def payu_form(request: Request) -> dict[str, str]:
    """PayU's form post, read with a size limit. Anything else (refund or dispute JSON) is empty."""
    body = await _body(request)
    if not request.headers.get("content-type", "").startswith("application/x-www-form-urlencoded"):
        return {}
    try:
        pairs = parse_qsl(
            body.decode("utf-8", "replace"), keep_blank_values=True, max_num_fields=150
        )
    except ValueError:
        return {}
    return {key: value for key, value in pairs if len(key) <= 64 and len(value) <= 4096}


async def payu_json(request: Request) -> dict[str, object]:
    body = await _body(request)
    try:
        value = json.loads(body or b"{}")
    except ValueError:
        return {}
    return value if isinstance(value, dict) else {}


PayUForm = Annotated[dict[str, str], Depends(payu_form)]


@router.post("/payu/return")
def payu_return(
    request: Request, session: DB, fields: PayUForm, background: BackgroundTasks
) -> RedirectResponse:
    """Where PayU sends the browser back (surl, furl and curl)."""
    settings = _settings(request)
    web = str(settings.web_app_url).rstrip("/") if settings.web_app_url else ""
    if not settings.billing_enabled:
        return RedirectResponse(f"{web}/plan", status_code=303)
    payment, reason = checkout.receive(session, settings, fields)
    if payment is None:
        logger.warning("billing.return_rejected", extra={"outcome": reason, "provider": "payu"})
        return RedirectResponse(f"{web}/plan?payment=unknown", status_code=303)
    if payment.status in {"started", "pending"}:
        background.add_task(
            checkout.confirm_soon, request.app.state.engine, settings, payment.txnid
        )
    path = "/pay" if payment.started_via == "link" else "/plan"
    return RedirectResponse(f"{web}{path}?payment={payment.id}", status_code=303)


@router.post("/payu/webhook", response_model=None)
def payu_webhook(request: Request, session: DB, fields: PayUForm) -> JSONResponse:
    """PayU's Successful and Failed payment events (form posts); refunds and disputes are logged."""
    settings = _settings(request)
    if not settings.billing_enabled or not fields:
        logger.info("billing.webhook", extra={"outcome": "ignored", "provider": "payu"})
        return JSONResponse({"received": True})
    payment, reason = checkout.receive(session, settings, fields)
    logger.info("billing.webhook", extra={"outcome": reason, "provider": "payu"})
    if reason == "bad_hash":
        return error_response(request, 400, "invalid_request", "Request could not be verified.")
    # Another app's payment on the same PayU account (wrong key or a txnid FinBoy did not make).
    return JSONResponse({"received": True})


@router.post("/payu/mandate")
def payu_mandate(
    request: Request,
    background: BackgroundTasks,
    notice: Annotated[dict[str, object], Depends(payu_json)],
) -> dict[str, bool]:
    """A bank's mandate cancellation or change; FinBoy checks PayU's own status before acting."""
    settings = _settings(request)
    mandate = next(
        (
            str(notice[name])
            for name in ("authPayuId", "authpayuid", "authPayuid")
            if isinstance(notice.get(name), (str, int))
        ),
        "",
    )
    if settings.billing_enabled and PAYU_ID.fullmatch(mandate):
        background.add_task(_bank_notice, request.app.state.engine, settings, mandate)
    return {"received": True}


def _bank_notice(engine: Engine, settings: Settings, mandate: str) -> None:
    with Session(engine) as session:
        mandates.on_bank_notice(session, settings, mandate)
