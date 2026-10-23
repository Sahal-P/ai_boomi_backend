"""Channel orchestration calls the shared assistant and speech service boundaries."""

import logging
import re
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from finboy.core.config import Settings
from finboy.core.errors import ProviderUnavailable
from finboy.core.languages import Language
from finboy.db.models.whatsapp import WhatsAppBinding, WhatsAppDelivery, WhatsAppReceipt
from finboy.services.assistant import service as assistant
from finboy.services.speech import service as speech
from finboy.services.whatsapp import receipts
from finboy.services.whatsapp.config import ChannelConfig
from finboy.services.whatsapp.events import InboundQuestion
from finboy.services.whatsapp.meta import InvalidMedia, MetaClient, MetaUnavailable, SendUnknown

logger = logging.getLogger(__name__)


def phone_text(text: str) -> str:
    """A phone cannot open the local unauthenticated review app on the demo computer."""
    return re.sub(
        r"https?://(?:localhost|127(?:\.[0-9]{1,3}){3}|0\.0\.0\.0|\[::1\])"
        r"(?=[:/\s)]|$)[^\s)]*",
        "the FinBoy review screen on the demo computer",
        text,
        flags=re.IGNORECASE,
    )


def language(value: str | None) -> Language | None:
    return value if value in {"en", "hi", "ml"} else None


def send_reply(
    session: Session,
    config: ChannelConfig,
    client: MetaClient,
    receipt: WhatsAppReceipt,
    question: InboundQuestion,
    *,
    text: str | None = None,
    media_id: str | None = None,
    allow_disabled: bool = False,
) -> bool:
    # Lock consent while admitting a send. A STOP that commits first blocks the send.
    binding = session.scalar(
        select(WhatsAppBinding).where(WhatsAppBinding.id == receipt.binding_id).with_for_update()
    )
    if binding is None or (not binding.enabled and not allow_disabled):
        session.rollback()
        return False
    if (
        question.sender not in config.allowlist
        or binding.user_id != config.allowlist[question.sender]
        or binding.sender_hash != config.digest("sender", question.sender)
    ):
        session.rollback()
        return False
    if question.provider_at < datetime.now(UTC) - timedelta(hours=24):
        session.rollback()
        return False
    kind = "text" if text is not None else "audio"
    delivery_id = session.scalar(
        insert(WhatsAppDelivery)
        .values(id=uuid4(), receipt_id=receipt.id, kind=kind, state="sending")
        .on_conflict_do_nothing(index_elements=[WhatsAppDelivery.receipt_id, WhatsAppDelivery.kind])
        .returning(WhatsAppDelivery.id)
    )
    session.commit()
    if delivery_id is None:
        return False
    delivery = session.get(WhatsAppDelivery, delivery_id)
    if delivery is None:
        return False
    # Persist sending before network I/O, then serialize consent through this send.
    binding = session.scalar(
        select(WhatsAppBinding)
        .where(WhatsAppBinding.id == receipt.binding_id)
        .execution_options(populate_existing=True)
        .with_for_update()
    )
    if binding is None or (not binding.enabled and not allow_disabled):
        delivery.state = "failed"
        session.commit()
        return False
    try:
        delivery.outbound_message_id = client.send(question.sender, text=text, media_id=media_id)
        delivery.state = "sent"
    except SendUnknown:
        delivery.state = "unknown"
    except MetaUnavailable:
        delivery.state = "failed"
    delivery.updated_at = datetime.now(UTC)
    session.commit()
    return delivery.state == "sent"


def process_question(
    factory: sessionmaker[Session],
    settings: Settings,
    config: ChannelConfig,
    receipt_id: UUID,
    question: InboundQuestion,
) -> None:
    client = MetaClient(config)
    try:
        with factory() as session:
            receipt = receipts.claim(session, receipt_id)
            if receipt is None:
                return
            binding = session.get(WhatsAppBinding, receipt.binding_id)
            if binding is None or (not binding.enabled and question.command != "stop"):
                receipts.finish(session, receipt_id, error="disabled")
                return
            if question.provider_at < datetime.now(UTC) - timedelta(hours=24):
                receipts.finish(session, receipt_id, error="window_expired")
                return
            preferred = language(binding.language)
            if question.command:
                response = {
                    "stop": (
                        "FinBoy WhatsApp replies are disabled. Send START to enable them again."
                    ),
                    "start": (
                        "FinBoy ledger questions are enabled. Send en, hi or ml "
                        "to choose a language. Send STOP to disable replies."
                    ),
                    "en": "English replies selected. Ask a question about your FinBoy ledger.",
                    "hi": "हिन्दी चुनी गई है। FinBoy के रिकॉर्ड के बारे में सवाल पूछें।",
                    "ml": "മലയാളം തിരഞ്ഞെടുത്തു. FinBoy രേഖകളെക്കുറിച്ച് ചോദിക്കാം.",
                }[question.command]
                ok = send_reply(
                    session,
                    config,
                    client,
                    receipt,
                    question,
                    text=response,
                    allow_disabled=question.command == "stop",
                )
                receipts.finish(session, receipt_id, error=None if ok else "provider_unavailable")
                return
            try:
                text = question.text
                if question.kind == "audio":
                    audio = client.download_audio(question.media_id or "", question.mime_type or "")
                    transcript = speech.transcribe_audio(
                        audio=audio.data,
                        content_type=audio.content_type,
                        settings=settings,
                        language_hint=preferred,
                    )
                    text = transcript.transcript
                if not 1 <= len(text.strip()) <= 2000:
                    raise ProviderUnavailable("invalid_audio")
                answer = assistant.answer_question(
                    session,
                    user_id=binding.user_id,
                    text=text,
                    display_style=preferred or "auto",
                    settings=settings,
                )
            except (ProviderUnavailable, MetaUnavailable) as exc:
                code = (
                    "invalid_audio"
                    if isinstance(exc, InvalidMedia)
                    or (isinstance(exc, ProviderUnavailable) and exc.code == "invalid_audio")
                    else "assistant_unavailable"
                )
                response = {
                    "en": (
                        "I could not process that question. Please send a short text question, "
                        "or use FinBoy on the demo computer."
                    ),
                    "hi": "यह सवाल अभी समझ नहीं पाया। छोटा टेक्स्ट सवाल भेजें या डेमो कंप्यूटर पर FinBoy खोलें।",
                    "ml": (
                        "ഈ ചോദ്യം ഇപ്പോൾ കൈകാര്യം ചെയ്യാനായില്ല. ചെറിയ ടെക്സ്റ്റ് ചോദ്യം അയയ്ക്കുക, "
                        "അല്ലെങ്കിൽ ഡെമോ കമ്പ്യൂട്ടറിൽ FinBoy തുറക്കുക."
                    ),
                }[preferred or "en"]
                session.rollback()
                send_reply(session, config, client, receipt, question, text=response)
                receipts.finish(session, receipt_id, error=code)
                return
            response = phone_text(answer.display_text)
            if len(response) > 4096:
                response = (
                    "Please view this answer in FinBoy on the demo computer. "
                    "The answer is too long for one WhatsApp reply."
                )
            text_sent = send_reply(session, config, client, receipt, question, text=response)
            if question.kind == "audio" and text_sent and 1 <= len(answer.speech_text) <= 600:
                try:
                    audio_reply = speech.synthesize_speech(
                        text=answer.speech_text, language=answer.speech_language, settings=settings
                    )
                    if audio_reply.media_type != "audio/mpeg":
                        raise InvalidMedia
                    media_id = client.upload_audio(audio_reply.data)
                    send_reply(session, config, client, receipt, question, media_id=media_id)
                except ProviderUnavailable, MetaUnavailable:
                    # Correct text has already been sent. Never fabricate an audio attachment.
                    logger.info("whatsapp.audio_unavailable", extra={"outcome": "text_only"})
            receipts.finish(
                session,
                receipt_id,
                error=None if text_sent else "provider_unavailable",
                language=answer.speech_language,
            )
    except Exception:
        # Background failures must not bubble into an accepted webhook or leak payloads.
        logger.error("whatsapp.processing_failed", extra={"outcome": "failed"})
        try:
            with factory() as session:
                session.rollback()
                receipts.finish(session, receipt_id, error="processing_failed")
        except Exception:
            logger.error("whatsapp.receipt_update_failed", extra={"outcome": "unavailable"})
    finally:
        client.close()
