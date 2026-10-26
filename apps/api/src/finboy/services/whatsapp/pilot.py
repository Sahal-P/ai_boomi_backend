"""Pilot household conversations: consent, one-tap decisions with undo, and Hindi voice.

Runs only for households with `users.pilot` (docs/pilot/contract.md). Each inbound message gets
at most one text-or-buttons reply plus one spoken reply. Nothing a household says is stored:
records go through the existing review decisions, and prompts keep only IDs and fingerprints.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from finboy.core.clock import today_ist
from finboy.core.config import Settings
from finboy.core.errors import ProviderUnavailable
from finboy.core.languages import Language
from finboy.db.models.ledger import Transaction
from finboy.db.models.whatsapp import WhatsAppBinding, WhatsAppPrompt, WhatsAppReceipt
from finboy.services.assistant import service as assistant
from finboy.services.ingestion.hindi_numbers import parse_amount
from finboy.services.money.models import Correction
from finboy.services.speech import service as speech
from finboy.services.speech.media import InvalidAudio
from finboy.services.ux import decisions
from finboy.services.ux.state import TaskError, data_version
from finboy.services.whatsapp import capture, hindi, prompts
from finboy.services.whatsapp.config import ChannelConfig
from finboy.services.whatsapp.events import InboundQuestion
from finboy.services.whatsapp.meta import InvalidMedia, MetaClient, MetaUnavailable

IST = ZoneInfo("Asia/Kolkata")
logger = logging.getLogger(__name__)
Reply = Callable[..., bool]


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
    change = prompts.pending_change(conversation.session, binding)
    if change is not None:
        return _changed_amount(conversation, change, text)
    return _answer(conversation, text)


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
    row = _record(conversation, prompt.transaction_id)
    if row is None or prompts.record_fingerprint(conversation.config, row) != prompt.fingerprint:
        return _changed(conversation, prompt.id, "record")
    prompts.answer(prompt)
    prompts.open_prompt(
        conversation.session,
        conversation.binding,
        "change_amount",
        transaction_id=row.id,
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


HANDLERS: dict[tuple[str, str], Callable[[Conversation, WhatsAppPrompt, str], str | None]] = {
    ("consent", "agree"): _consent,
    ("consent", "decline"): _consent,
    ("confirm", "yes"): _decide,
    ("confirm", "no"): _decide,
    ("confirm", "change"): _ask_amount,
    ("undo", "undo"): _undo,
}
