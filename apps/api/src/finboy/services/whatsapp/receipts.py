"""PostgreSQL transaction boundaries and atomic admission/claims."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from finboy.core.config import LOCAL_USER_ID
from finboy.db.models.core import User
from finboy.db.models.whatsapp import (
    WhatsAppBinding,
    WhatsAppDelivery,
    WhatsAppReceipt,
    WhatsAppReminder,
)
from finboy.services.whatsapp.config import ChannelConfig
from finboy.services.whatsapp.events import InboundQuestion, Status


@dataclass(frozen=True)
class Admission:
    receipt_id: UUID
    question: InboundQuestion


def interrupt_stale(session: Session, *, before: datetime) -> None:
    """No replay is possible: raw questions/audio were never retained."""
    session.execute(
        update(WhatsAppReceipt)
        .where(
            WhatsAppReceipt.state.in_(["admitted", "processing"]),
            WhatsAppReceipt.received_at < before,
        )
        .values(state="interrupted", error_code="interrupted", completed_at=datetime.now(UTC))
    )
    # A DB failure after Meta accepted a send may also leave an already failed receipt.
    session.execute(
        update(WhatsAppDelivery)
        .where(WhatsAppDelivery.state == "sending", WhatsAppDelivery.created_at < before)
        .values(state="unknown", updated_at=datetime.now(UTC))
    )
    session.commit()


def admit(
    session: Session,
    config: ChannelConfig,
    questions: list[InboundQuestion],
    statuses: list[Status],
) -> list[Admission]:
    now = datetime.now(UTC)
    interrupt_stale(session, before=now - timedelta(minutes=10))
    admitted: list[Admission] = []
    for question in questions:
        user = config.allowlist.get(question.sender)
        if user is None:
            continue
        # Fail closed: a household must exist, and any household other than the owner's must
        # be an enrolled pilot (docs/pilot/contract.md).
        pilot = session.scalar(select(User.pilot).where(User.id == user))
        if pilot is None or (user != LOCAL_USER_ID and pilot is not True):
            continue
        sender_hash = config.digest("sender", question.sender)
        session.execute(
            insert(WhatsAppBinding)
            .values(
                id=uuid4(),
                user_id=user,
                sender_hash=sender_hash,
                enabled=True,
                # Village pilot households speak Hindi; the owner keeps automatic detection.
                language="hi" if user != LOCAL_USER_ID else None,
                last_inbound_at=question.provider_at,
            )
            .on_conflict_do_nothing(index_elements=[WhatsAppBinding.sender_hash])
        )
        binding = session.scalar(
            select(WhatsAppBinding)
            .where(WhatsAppBinding.sender_hash == sender_hash, WhatsAppBinding.user_id == user)
            .with_for_update()
        )
        if binding is None:
            continue
        command = question.command
        older = question.provider_at < binding.last_inbound_at
        stale = (
            question.provider_at < now - timedelta(hours=24)
            or question.provider_at > now + timedelta(minutes=5)
            or (command is not None and older)
        )
        state = (
            "ignored"
            if stale or (not binding.enabled and command not in {"start", "stop"})
            else "admitted"
        )
        receipt_id = session.scalar(
            insert(WhatsAppReceipt)
            .values(
                id=uuid4(),
                binding_id=binding.id,
                inbound_message_id=question.message_id,
                content_hash=config.digest(
                    "content", question.text or question.media_id or question.button_id or ""
                ),
                kind="command" if command else question.kind,
                language=binding.language,
                state=state,
                error_code="stale_message" if stale else "disabled" if state == "ignored" else None,
                provider_at=question.provider_at,
            )
            .on_conflict_do_nothing(index_elements=[WhatsAppReceipt.inbound_message_id])
            .returning(WhatsAppReceipt.id)
        )
        if receipt_id is None:
            continue
        if not stale and not older:
            binding.last_inbound_at = question.provider_at
            binding.updated_at = now
            if command in {"start", "stop"}:
                binding.enabled = command == "start"
            elif command in {"en", "hi", "ml"} and binding.enabled:
                binding.language = command
        if state == "admitted":
            admitted.append(Admission(receipt_id, question))
    for status in statuses:
        # Provider status can only touch a known outbound message for this approved binding.
        row = session.execute(
            select(WhatsAppDelivery, WhatsAppBinding.sender_hash)
            .join(WhatsAppReceipt, WhatsAppReceipt.id == WhatsAppDelivery.receipt_id)
            .join(WhatsAppBinding, WhatsAppBinding.id == WhatsAppReceipt.binding_id)
            .where(WhatsAppDelivery.outbound_message_id == status.id)
            .with_for_update(of=WhatsAppDelivery)
        ).first()
        if row is None:
            # A pilot reminder template FinBoy sent first, outside any reply.
            row = session.execute(
                select(WhatsAppReminder, WhatsAppBinding.sender_hash)
                .join(WhatsAppBinding, WhatsAppBinding.id == WhatsAppReminder.binding_id)
                .where(WhatsAppReminder.outbound_message_id == status.id)
                .with_for_update(of=WhatsAppReminder)
            ).first()
        if row is None or row[1] != config.digest("sender", status.recipient_id):
            continue
        sent = row[0]
        rank = {None: 0, "sent": 1, "failed": 2, "delivered": 3, "read": 4}
        if rank[status.status] > rank[sent.provider_status] or sent.provider_status is None:
            sent.provider_status = status.status
            sent.updated_at = now
    session.commit()
    return admitted


def claim(session: Session, receipt_id: UUID) -> WhatsAppReceipt | None:
    receipt = session.scalar(
        update(WhatsAppReceipt)
        .where(WhatsAppReceipt.id == receipt_id, WhatsAppReceipt.state == "admitted")
        .values(state="processing", claimed_at=datetime.now(UTC))
        .returning(WhatsAppReceipt)
    )
    session.commit()
    return receipt


def finish(
    session: Session, receipt_id: UUID, *, error: str | None = None, language: str | None = None
) -> None:
    values: dict[str, object] = {
        "state": "failed" if error else "completed",
        "error_code": error,
        "completed_at": datetime.now(UTC),
    }
    if language is not None:
        values["language"] = language
    session.execute(
        update(WhatsAppReceipt)
        .where(WhatsAppReceipt.id == receipt_id, WhatsAppReceipt.state == "processing")
        .values(**values)
    )
    session.commit()
