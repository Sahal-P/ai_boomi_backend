"""Pilot household conversations: consent, one-tap decisions with undo, and Hindi voice.

Runs only for households with `users.pilot` (docs/pilot/contract.md). Each inbound message gets
at most one text-or-buttons reply plus one spoken reply. Nothing a household says is stored:
records go through the existing review decisions, and prompts keep only IDs and fingerprints.
"""

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from finboy.core.clock import today_ist
from finboy.core.config import Settings
from finboy.core.errors import ProviderUnavailable
from finboy.core.languages import Language
from finboy.db.models.ledger import Commitment, Transaction
from finboy.db.models.whatsapp import WhatsAppBinding, WhatsAppPrompt, WhatsAppReceipt
from finboy.services.assistant import service as assistant
from finboy.services.ingestion.hindi_numbers import parse_amount
from finboy.services.money.engine import PeriodSpec, money_summary, upcoming_commitments
from finboy.services.money.models import Correction
from finboy.services.speech import service as speech
from finboy.services.speech.media import InvalidAudio
from finboy.services.ux import decisions
from finboy.services.ux.obligations import ObligationCorrection, correct_obligation
from finboy.services.ux.state import TaskError, data_version
from finboy.services.whatsapp import capture, hindi, prompts, reminders, statement
from finboy.services.whatsapp.config import ChannelConfig
from finboy.services.whatsapp.events import InboundQuestion
from finboy.services.whatsapp.meta import InvalidMedia, MetaClient, MetaUnavailable

IST = ZoneInfo("Asia/Kolkata")
logger = logging.getLogger(__name__)
Reply = Callable[..., bool]
WEEK = re.compile(
    r"\s*(?:मेरा\s+|my\s+)?(?:हिसाब|हिसाब-किताब|hisaab|hisab)"
    r"(?:\s+(?:बताओ|बताइए|बताइये|दिखाओ|दिखाइए|दो|दीजिए|batao|dikhao))?\s*[।.!?]*\s*",
    re.IGNORECASE,
)


@dataclass
class Conversation:
    session: Session
    settings: Settings
    config: ChannelConfig
    client: MetaClient
    receipt: WhatsAppReceipt
    question: InboundQuestion
    binding: WhatsAppBinding
    reply: Reply  # processor.send_reply: consent lock, allowlist, 24-hour window, idempotency

    def send(self, text: str, buttons: list[tuple[str, str]] | None = None) -> bool:
        return self.reply(
            self.session,
            self.config,
            self.client,
            self.receipt,
            self.question,
            text=text,
            buttons=buttons,
        )

    def speak(self, text: str, language: Language = "hi") -> None:
        """Best effort after the written reply; never fabricate or retry audio."""
        try:
            audio = speech.synthesize_speech(text=text, language=language, settings=self.settings)
            if audio.media_type != "audio/mpeg":
                raise InvalidMedia
            media_id = self.client.upload_audio(audio.data)
            self.reply(
                self.session,
                self.config,
                self.client,
                self.receipt,
                self.question,
                media_id=media_id,
            )
        except ProviderUnavailable, MetaUnavailable, InvalidAudio:
            logger.info("whatsapp.pilot_audio_unavailable", extra={"outcome": "text_only"})

    def done(self, sent: bool, error: str | None = None) -> str | None:
        return error or (None if sent else "provider_unavailable")


def handle(conversation: Conversation) -> str | None:
    """Returns the receipt error code (None when the household got a correct reply)."""
    error = _handle(conversation)
    if conversation.binding.consented_at is not None:
        _remind(conversation)
    return error


def _handle(conversation: Conversation) -> str | None:
    question, binding = conversation.question, conversation.binding
    if question.kind == "button":
        return _tap(conversation)
    if binding.consented_at is None:
        return _ask_consent(conversation)
    if question.kind == "image":
        return _screenshot(conversation)
    try:
        text = _heard(conversation)
    except ProviderUnavailable, MetaUnavailable, InvalidAudio:
        conversation.session.rollback()
        sent = conversation.send("आवाज़ साफ़ नहीं आई। फिर से बोलिए या लिखिए।")
        return conversation.done(sent, "invalid_audio")
    if WEEK.fullmatch(text):
        return _week(conversation)
    change = prompts.pending_change(conversation.session, binding)
    if change is not None:
        return _changed_amount(conversation, change, text)
    try:
        reading = statement.read_statement(text, conversation.settings, today_ist())
    except ProviderUnavailable:
        conversation.session.rollback()
        sent = conversation.send(hindi.UNAVAILABLE)
        return conversation.done(sent, "statement_unavailable")
    if reading.kind == "question":
        return _answer(conversation, text)
    if reading.kind == "unclear":
        return _say(conversation, hindi.UNCLEAR, hindi.UNCLEAR_SPEECH)
    if reading.amount_minor is None:
        return _say(
            conversation, hindi.AMOUNT_MISSING, hindi.AMOUNT_MISSING_SPEECH, "amount_unclear"
        )
    if reading.kind == "due":
        return _save_due(conversation, reading)
    return _record_money(conversation, reading)


def _say(conversation: Conversation, text: str, spoken: str, error: str | None = None):
    conversation.session.rollback()
    sent = conversation.send(text)
    if sent:
        conversation.speak(spoken)
    return conversation.done(sent, error)


def _heard(conversation: Conversation) -> str:
    question = conversation.question
    text = question.text
    if question.kind == "audio":
        audio = conversation.client.download_audio(
            question.media_id or "", question.mime_type or ""
        )
        text = speech.transcribe_audio(
            audio=audio.data,
            content_type=audio.content_type,
            settings=conversation.settings,
            language_hint="hi",
        ).transcript
    if not 1 <= len(text.strip()) <= 2000:
        raise ProviderUnavailable("invalid_audio")
    return text


def _ask_consent(conversation: Conversation) -> str | None:
    prompt = prompts.open_prompt(conversation.session, conversation.binding, "consent")
    conversation.session.commit()
    sent = conversation.send(
        hindi.CONSENT,
        [
            (prompts.button(prompt, "agree"), hindi.AGREE),
            (prompts.button(prompt, "decline"), hindi.DECLINE),
        ],
    )
    if sent:
        conversation.speak(hindi.CONSENT_SPEECH)
    return conversation.done(sent)


def _tap(conversation: Conversation) -> str | None:
    session, binding = conversation.session, conversation.binding
    parsed = prompts.parse(conversation.question.button_id or "")
    prompt = prompts.claim(session, binding, parsed[0]) if parsed else None
    handler = HANDLERS.get((prompt.purpose, parsed[1])) if prompt and parsed else None
    if prompt is None or parsed is None or handler is None:
        session.rollback()
        return conversation.done(conversation.send(hindi.EXPIRED), "prompt_expired")
    if prompt.purpose != "consent" and binding.consented_at is None:
        session.rollback()
        return _ask_consent(conversation)
    return handler(conversation, prompt, parsed[1])


def _consent(conversation: Conversation, prompt: WhatsAppPrompt, choice: str) -> str | None:
    prompts.answer(prompt)
    if choice == "agree":
        conversation.binding.consented_at = datetime.now(UTC)
    conversation.session.commit()
    if choice != "agree":
        return conversation.done(conversation.send(hindi.DECLINED))
    sent = conversation.send(hindi.WELCOME)
    if sent:
        conversation.speak(hindi.WELCOME_SPEECH)
    return conversation.done(sent)


def _record(conversation: Conversation, transaction_id: UUID | None) -> Transaction | None:
    if transaction_id is None:
        return None
    return conversation.session.scalar(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == conversation.binding.user_id,
        )
    )


def _payee(merchant: str | None) -> str | None:
    if not merchant or "[address]" in merchant or merchant.lower().startswith("unknown"):
        return None
    return merchant


def _day(row: Transaction) -> date:
    return row.occurred_at.astimezone(IST).date() if row.occurred_at else today_ist()


def _changed(conversation: Conversation, prompt_id: UUID, error: str) -> str | None:
    """The record moved on since the card: stop that card and say so."""
    session = conversation.session
    session.rollback()
    stale = session.get(WhatsAppPrompt, prompt_id, with_for_update=True)
    if stale is not None and stale.state in {"open", "answered"}:
        stale.state = "expired"
    session.commit()
    message = hindi.UNDO_REFUSED if error == "undo" else hindi.CHANGED
    return conversation.done(conversation.send(message), "record_changed")


def offer_card(conversation: Conversation, transaction_id: UUID, prefix: str = "") -> str | None:
    """The confirm card for a record waiting for review, in text and voice."""
    session, binding = conversation.session, conversation.binding
    row = _record(conversation, transaction_id)
    if row is None or row.status != "needs_review":
        session.rollback()
        return conversation.done(conversation.send(prefix + hindi.CHANGED), "record_changed")
    prompt = prompts.open_prompt(
        session,
        binding,
        "confirm",
        transaction_id=row.id,
        fingerprint=prompts.record_fingerprint(conversation.config, row),
    )
    text, spoken = hindi.record_card(
        amount_minor=row.amount_minor,
        out=row.direction == "out",
        counterparty=_payee(row.merchant),
        day=_day(row),
        category=row.category,
        today=today_ist(),
    )
    session.commit()
    sent = conversation.send(
        prefix + text,
        [
            (prompts.button(prompt, "yes"), hindi.YES),
            (prompts.button(prompt, "change"), hindi.CHANGE),
            (prompts.button(prompt, "no"), hindi.NO),
        ],
    )
    if sent:
        conversation.speak(spoken)
    return conversation.done(sent)


def _decide(conversation: Conversation, prompt: WhatsAppPrompt, choice: str) -> str | None:
    if prompt.commitment_id is not None:
        return _decide_due(conversation, prompt, choice)
    session, binding = conversation.session, conversation.binding
    row = _record(conversation, prompt.transaction_id)
    if row is None or prompts.record_fingerprint(conversation.config, row) != prompt.fingerprint:
        return _changed(conversation, prompt.id, "record")
    amount, out, payee = row.amount_minor, row.direction == "out", _payee(row.merchant)
    prompt_id = prompt.id
    prompts.answer(prompt)
    try:
        result = decisions.decide(
            session,
            user_id=binding.user_id,
            transaction_id=row.id,
            request=decisions.DecisionRequest(
                action="confirm" if choice == "yes" else "reject",
                expected_version=data_version(session, binding.user_id),
            ),
        )
    except TaskError:
        return _changed(conversation, prompt_id, "record")
    undo = prompts.open_prompt(
        session, binding, "undo", transaction_id=row.id, decision_id=result.decision_id
    )
    session.commit()
    text = hindi.confirmed(amount, out, payee) if choice == "yes" else hindi.REJECTED
    sent = conversation.send(text, [(prompts.button(undo, "undo"), hindi.UNDO)])
    if sent:
        conversation.speak("जोड़ दिया।" if choice == "yes" else "नहीं जोड़ा।")
    return conversation.done(sent)


def _ask_amount(conversation: Conversation, prompt: WhatsAppPrompt, _choice: str) -> str | None:
    if prompt.commitment_id is not None:
        due = _due_row(conversation, prompt.commitment_id)
        current = prompts.due_fingerprint(conversation.config, due) if due else None
    else:
        row = _record(conversation, prompt.transaction_id)
        current = prompts.record_fingerprint(conversation.config, row) if row else None
    if current is None or current != prompt.fingerprint:
        return _changed(conversation, prompt.id, "record")
    prompts.answer(prompt)
    prompts.open_prompt(
        conversation.session,
        conversation.binding,
        "change_amount",
        transaction_id=prompt.transaction_id,
        commitment_id=prompt.commitment_id,
        fingerprint=prompt.fingerprint,
    )
    conversation.session.commit()
    sent = conversation.send(hindi.CHANGE_ASK)
    if sent:
        conversation.speak(hindi.CHANGE_ASK_SPEECH)
    return conversation.done(sent)


def _changed_amount(conversation: Conversation, change: WhatsAppPrompt, text: str) -> str | None:
    """The reply after "रकम बदलें" is read only as an amount, then the card comes back."""
    session, binding = conversation.session, conversation.binding
    amount = parse_amount(text)
    if amount is None:
        session.rollback()
        return conversation.done(conversation.send(hindi.AMOUNT_UNCLEAR), "amount_unclear")
    if change.commitment_id is not None:
        return _changed_due_amount(conversation, change, amount)
    row = _record(conversation, change.transaction_id)
    if row is None or prompts.record_fingerprint(conversation.config, row) != change.fingerprint:
        return _changed(conversation, change.id, "record")
    change_id, transaction_id = change.id, row.id
    prompts.answer(change)
    if amount != row.amount_minor:
        try:
            decisions.decide(
                session,
                user_id=binding.user_id,
                transaction_id=transaction_id,
                request=decisions.DecisionRequest(
                    action="correct",
                    correction=Correction(amount_minor=amount),
                    expected_version=data_version(session, binding.user_id),
                ),
            )
        except TaskError:
            return _changed(conversation, change_id, "record")
    else:
        session.commit()
    return offer_card(conversation, transaction_id)


def _undo(conversation: Conversation, prompt: WhatsAppPrompt, _choice: str) -> str | None:
    if prompt.commitment_id is not None:
        return _undo_due(conversation, prompt)
    session, binding = conversation.session, conversation.binding
    prompt_id, transaction_id, decision_id = prompt.id, prompt.transaction_id, prompt.decision_id
    if transaction_id is None or decision_id is None:
        return _changed(conversation, prompt_id, "undo")
    prompts.answer(prompt)
    try:
        decisions.undo_decision(
            session,
            user_id=binding.user_id,
            transaction_id=transaction_id,
            decision_id=decision_id,
            expected_version=data_version(session, binding.user_id),
        )
    except TaskError:
        return _changed(conversation, prompt_id, "undo")
    return offer_card(conversation, transaction_id, prefix=hindi.UNDONE + "\n\n")


def _screenshot(conversation: Conversation) -> str | None:
    session = conversation.session
    # End this read snapshot; the import pipeline commits through its own sessions.
    session.rollback()
    result = capture.capture_screenshot(
        session.get_bind(),
        conversation.settings,
        conversation.client,
        conversation.question,
        conversation.binding.user_id,
    )
    if result.outcome == "saved" and result.transaction_id is not None:
        return offer_card(conversation, result.transaction_id)
    sent = conversation.send(capture.capture_reply(result, "hi"))
    return conversation.done(sent, capture.RECEIPT_ERRORS.get(result.outcome))


def _answer(conversation: Conversation, text: str) -> str | None:
    """Questions use the shared assistant: engine figures, Hindi wording, spoken reply."""
    from finboy.services.whatsapp.processor import phone_text

    session, binding = conversation.session, conversation.binding
    try:
        answer = assistant.answer_question(
            session,
            user_id=binding.user_id,
            text=text,
            display_style=binding.language or "hi",
            settings=conversation.settings,
        )
    except ProviderUnavailable:
        session.rollback()
        return conversation.done(conversation.send(hindi.UNAVAILABLE), "assistant_unavailable")
    response = phone_text(answer.display_text)
    sent = conversation.send(response if len(response) <= 4096 else hindi.UNAVAILABLE)
    if sent and 1 <= len(answer.speech_text) <= 600:
        conversation.speak(answer.speech_text, answer.speech_language)
    return conversation.done(sent)


def _record_money(conversation: Conversation, reading: statement.Statement) -> str | None:
    """Money spent or received, said by voice: one line through review, then the card."""
    session, question = conversation.session, conversation.question
    session.rollback()  # end this read snapshot; the import pipeline commits on its own
    result = capture.record_voice(
        session.get_bind(),
        conversation.settings,
        user_id=conversation.binding.user_id,
        message_id=question.message_id,
        line=statement.payment_line(reading, question.provider_at),
        received_at=question.provider_at,
        category=reading.category,
    )
    row = _record(conversation, result.transaction_id)
    if row is not None and row.status == "needs_review":
        return offer_card(conversation, row.id)
    if row is not None and row.status == "confirmed":
        return conversation.done(conversation.send(hindi.ALREADY))
    if result.outcome == "busy":
        return conversation.done(conversation.send(hindi.BUSY), "capture_busy")
    return conversation.done(conversation.send(hindi.UNAVAILABLE), "capture_unavailable")


def _week(conversation: Conversation) -> str | None:
    """The reply to हिसाब: engine figures for Monday to today, plus dues in the next 7 days."""
    session, user_id = conversation.session, conversation.binding.user_id
    today = today_ist()
    monday = today - timedelta(days=today.weekday())
    summary = money_summary(
        session,
        user_id=user_id,
        period=PeriodSpec(kind="range", start_date=monday, end_date=today),
    )
    ahead = upcoming_commitments(
        session,
        user_id=user_id,
        period=PeriodSpec(kind="range", start_date=today, end_date=today + timedelta(days=7)),
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
        return _say(conversation, hindi.WEEK_EMPTY, hindi.WEEK_EMPTY_SPEECH)
    text, spoken = hindi.week(
        income=summary.tracked_income_minor,
        outflow=summary.confirmed_outflows_minor,
        top=top[:3],
        dues=dues,
        overdue=summary.overdue_commitments_minor,
        waiting=summary.pending_review_count,
    )
    sent = conversation.send(text)
    if sent:
        conversation.speak(spoken)
    return conversation.done(sent)


def _due_row(conversation: Conversation, commitment_id: UUID | None) -> Commitment | None:
    if commitment_id is None:
        return None
    return conversation.session.scalar(
        select(Commitment).where(
            Commitment.id == commitment_id,
            Commitment.user_id == conversation.binding.user_id,
            Commitment.dataset == "household",
        )
    )


def _save_due(conversation: Conversation, reading: statement.Statement) -> str | None:
    """A spoken due is kept as `pending` (never counted) until the household taps हाँ."""
    if reading.due_date is None or reading.amount_minor is None:
        return _say(conversation, hindi.DUE_DAY_MISSING, hindi.DUE_DAY_MISSING_SPEECH)
    row = Commitment(
        id=uuid4(),
        user_id=conversation.binding.user_id,
        kind="loan",
        label=reading.label or "किस्त",
        amount_minor=reading.amount_minor,
        due_date=reading.due_date,
        status="pending",
        confidence=Decimal("1.000"),
        user_resolved=False,
    )
    conversation.session.add(row)
    conversation.session.flush()
    return offer_due_card(conversation, row.id)


def offer_due_card(conversation: Conversation, commitment_id: UUID, prefix: str = "") -> str | None:
    session, binding = conversation.session, conversation.binding
    row = _due_row(conversation, commitment_id)
    if row is None or row.status != "pending":
        session.rollback()
        return conversation.done(conversation.send(prefix + hindi.CHANGED), "record_changed")
    prompt = prompts.open_prompt(
        session,
        binding,
        "confirm",
        commitment_id=row.id,
        fingerprint=prompts.due_fingerprint(conversation.config, row),
    )
    text, spoken = hindi.due_card(amount_minor=row.amount_minor, label=row.label, due=row.due_date)
    session.commit()
    sent = conversation.send(
        prefix + text,
        [
            (prompts.button(prompt, "yes"), hindi.YES),
            (prompts.button(prompt, "change"), hindi.CHANGE),
            (prompts.button(prompt, "no"), hindi.NO),
        ],
    )
    if sent:
        conversation.speak(spoken)
    return conversation.done(sent)


def _decide_due(conversation: Conversation, prompt: WhatsAppPrompt, choice: str) -> str | None:
    session, binding = conversation.session, conversation.binding
    row = _due_row(conversation, prompt.commitment_id)
    if (
        row is None
        or row.status != "pending"
        or prompts.due_fingerprint(conversation.config, row) != prompt.fingerprint
    ):
        return _changed(conversation, prompt.id, "record")
    prompts.answer(prompt)
    row.status = "upcoming" if choice == "yes" else "dismissed"
    row.user_resolved = choice != "yes"
    session.flush()
    undo = prompts.open_prompt(
        session,
        binding,
        "undo",
        commitment_id=row.id,
        fingerprint=prompts.due_fingerprint(conversation.config, row),
    )
    buttons = [(prompts.button(undo, "undo"), hindi.UNDO)]
    text = hindi.due_saved(row.amount_minor, row.label, row.due_date)
    if choice != "yes":
        text = hindi.REJECTED
    elif binding.reminders_opt_in_at is None:
        # Asked once, after the household's first due; reminders are strictly opt-in.
        opt_in = prompts.open_prompt(session, binding, "reminder_opt_in")
        buttons.insert(0, (prompts.button(opt_in, "remind"), hindi.REMIND))
        text += "\n\n" + hindi.REMIND_ASK
    session.commit()
    sent = conversation.send(text, buttons)
    if sent:
        conversation.speak("याद रख लिया।" if choice == "yes" else "नहीं जोड़ा।")
    return conversation.done(sent)


def _changed_due_amount(conversation: Conversation, change: WhatsAppPrompt, amount: int):
    row = _due_row(conversation, change.commitment_id)
    if (
        row is None
        or row.status != "pending"
        or prompts.due_fingerprint(conversation.config, row) != change.fingerprint
    ):
        return _changed(conversation, change.id, "record")
    prompts.answer(change)
    row.amount_minor = amount  # still pending: nothing counts until हाँ
    conversation.session.flush()
    return offer_due_card(conversation, row.id)


def _undo_due(conversation: Conversation, prompt: WhatsAppPrompt) -> str | None:
    row = _due_row(conversation, prompt.commitment_id)
    if (
        row is None
        or row.status not in {"upcoming", "dismissed"}
        or prompts.due_fingerprint(conversation.config, row) != prompt.fingerprint
    ):
        return _changed(conversation, prompt.id, "undo")
    prompts.answer(prompt)
    row.status, row.user_resolved = "pending", False
    conversation.session.flush()
    return offer_due_card(conversation, row.id, prefix=hindi.UNDONE + "\n\n")


def _reminders(conversation: Conversation, prompt: WhatsAppPrompt, _choice: str) -> str | None:
    prompts.answer(prompt)
    conversation.binding.reminders_opt_in_at = datetime.now(UTC)
    conversation.session.commit()
    sent = conversation.send(hindi.REMINDERS_ON)
    if sent:
        conversation.speak(hindi.REMINDERS_ON)
    return conversation.done(sent)


def _remind(conversation: Conversation) -> None:
    """Without a reminder template, a due coming up follows the reply as its own card."""
    session, binding = conversation.session, conversation.binding
    session.rollback()
    today = today_ist()
    due = reminders.fallback_due(session, conversation.settings, binding, today)
    reminder = reminders.claim(session, due, "sending") if due else None
    if due is None or reminder is None:
        session.rollback()
        return
    row = due.commitment
    prompt = prompts.open_prompt(
        session,
        binding,
        "due_paid",
        commitment_id=row.id,
        fingerprint=prompts.due_fingerprint(conversation.config, row),
    )
    text = hindi.due_notice(row.amount_minor, row.label, row.due_date, today)
    buttons = [
        (prompts.button(prompt, "paid"), hindi.PAID),
        (prompts.button(prompt, "later"), hindi.LATER),
    ]
    session.commit()
    sent = conversation.reply(
        session,
        conversation.config,
        conversation.client,
        conversation.receipt,
        conversation.question,
        text=text,
        buttons=buttons,
        reminder=True,
    )
    reminder.state = "sent" if sent else "failed"
    reminder.updated_at = datetime.now(UTC)
    session.commit()


def _reopen(session: Session, prompt_id: UUID) -> None:
    """Nothing was recorded, so the same button may be tapped again."""
    session.rollback()
    prompt = session.get(WhatsAppPrompt, prompt_id, with_for_update=True)
    if prompt is not None and prompt.state == "answered":
        prompt.state, prompt.answered_at = "open", None
    session.commit()


def _paid(conversation: Conversation, prompt: WhatsAppPrompt, _choice: str) -> str | None:
    """Records the payment as a confirmed outflow and links it to the due.

    The due then stops being deducted, so money left falls only by the amount actually paid.
    `decide` may already link it (payee equals the due label); `correct_obligation` makes sure.
    """
    session, binding, question = conversation.session, conversation.binding, conversation.question
    row = _due_row(conversation, prompt.commitment_id)
    if row is not None and row.status == "paid":
        prompts.answer(prompt)
        session.commit()
        return conversation.done(conversation.send(hindi.ALREADY_PAID))
    if (
        row is None
        or row.status != "upcoming"
        or prompts.due_fingerprint(conversation.config, row) != prompt.fingerprint
    ):
        return _changed(conversation, prompt.id, "record")
    prompt_id, due_id, amount, label = prompt.id, row.id, row.amount_minor, row.label
    prompts.answer(prompt)  # committed first: a second tap cannot record a second payment
    session.commit()
    payment = statement.Statement("spent", amount, label, "unknown", today_ist(), "loan_emi")
    result = capture.record_voice(
        session.get_bind(),
        conversation.settings,
        user_id=binding.user_id,
        message_id=question.message_id,
        line=statement.payment_line(payment, question.provider_at),
        received_at=question.provider_at,
        category="loan_emi",
    )
    paid = _record(conversation, result.transaction_id)
    if paid is None or paid.amount_minor != amount or paid.direction != "out":
        _reopen(session, prompt_id)
        if result.outcome == "busy":
            return conversation.done(conversation.send(hindi.BUSY), "capture_busy")
        return conversation.done(conversation.send(hindi.UNAVAILABLE), "capture_unavailable")
    paid_id = paid.id
    try:
        if paid.status == "needs_review":
            decisions.decide(
                session,
                user_id=binding.user_id,
                transaction_id=paid_id,
                request=decisions.DecisionRequest(
                    action="confirm", expected_version=data_version(session, binding.user_id)
                ),
            )
        correct_obligation(
            session,
            user_id=binding.user_id,
            obligation_id=due_id,
            request=ObligationCorrection(
                expected_version=data_version(session, binding.user_id),
                status="paid",
                paid_transaction_id=paid_id,
            ),
        )
    except TaskError:
        return _changed(conversation, prompt_id, "record")
    repeat = prompts.open_prompt(session, binding, "due_repeat", commitment_id=due_id)
    session.commit()
    sent = conversation.send(
        hindi.paid_done(amount, label) + "\n\n" + hindi.REPEAT_ASK,
        [
            (prompts.button(repeat, "again"), hindi.AGAIN),
            (prompts.button(repeat, "skip"), hindi.NO),
        ],
    )
    if sent:
        conversation.speak("जोड़ दिया। अगले महीने भी यही देना है?")
    return conversation.done(sent)


def _later(conversation: Conversation, _prompt: WhatsAppPrompt, _choice: str) -> str | None:
    """The reminder's "भर दिया" button stays usable until the household has paid."""
    conversation.session.commit()
    return conversation.done(conversation.send(hindi.LATER_OK))


def _next_month(day: date) -> date:
    first = (day.replace(day=1) + timedelta(days=32)).replace(day=1)
    following = (first + timedelta(days=32)).replace(day=1)
    return first.replace(day=min(day.day, (following - timedelta(days=1)).day))


def _repeat(conversation: Conversation, prompt: WhatsAppPrompt, choice: str) -> str | None:
    """Next month's due is saved directly: the household just said it repeats. Undoable."""
    session = conversation.session
    row = _due_row(conversation, prompt.commitment_id)
    prompts.answer(prompt)
    if choice != "again" or row is None:
        session.commit()
        return conversation.done(conversation.send(hindi.OK))
    following = Commitment(
        id=uuid4(),
        user_id=conversation.binding.user_id,
        kind=row.kind,
        label=row.label,
        amount_minor=row.amount_minor,
        due_date=_next_month(row.due_date),
        status="upcoming",
        confidence=Decimal("1.000"),
        user_resolved=False,
    )
    session.add(following)
    session.flush()
    undo = prompts.open_prompt(
        session,
        conversation.binding,
        "undo",
        commitment_id=following.id,
        fingerprint=prompts.due_fingerprint(conversation.config, following),
    )
    session.commit()
    sent = conversation.send(
        hindi.due_saved(following.amount_minor, following.label, following.due_date),
        [(prompts.button(undo, "undo"), hindi.UNDO)],
    )
    if sent:
        conversation.speak("याद रख लिया।")
    return conversation.done(sent)


HANDLERS: dict[tuple[str, str], Callable[[Conversation, WhatsAppPrompt, str], str | None]] = {
    ("consent", "agree"): _consent,
    ("consent", "decline"): _consent,
    ("confirm", "yes"): _decide,
    ("confirm", "no"): _decide,
    ("confirm", "change"): _ask_amount,
    ("undo", "undo"): _undo,
    ("reminder_opt_in", "remind"): _reminders,
    ("due_paid", "paid"): _paid,
    ("due_paid", "later"): _later,
    ("due_repeat", "again"): _repeat,
    ("due_repeat", "skip"): _repeat,
}
