"""Channel orchestration calls the shared assistant and speech service boundaries."""

import logging
import re
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, sessionmaker

from finboy.core.config import Settings
from finboy.core.errors import AccessError, ProviderUnavailable
from finboy.core.languages import Language
from finboy.db.models.core import User
from finboy.db.models.whatsapp import (
    WhatsAppBinding,
    WhatsAppDelivery,
    WhatsAppPrompt,
    WhatsAppReceipt,
)
from finboy.services.accounts import households, login, usage
from finboy.services.assistant import service as assistant
from finboy.services.speech import service as speech
from finboy.services.speech.media import InvalidAudio
from finboy.services.whatsapp import capture, pilot, prompts, receipts, signup
from finboy.services.whatsapp.config import ChannelConfig
from finboy.services.whatsapp.events import InboundQuestion
from finboy.services.whatsapp.language import written_language
from finboy.services.whatsapp.meta import (
    InvalidMedia,
    Listing,
    MetaClient,
    MetaUnavailable,
    SendUnknown,
)

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
    buttons: list[tuple[str, str]] | None = None,
    listing: Listing | None = None,
    allow_disabled: bool = False,
    reminder: bool = False,
) -> bool:
    # Lock consent while admitting a send. A STOP that commits first blocks the send.
    binding = session.scalar(
        select(WhatsAppBinding).where(WhatsAppBinding.id == receipt.binding_id).with_for_update()
    )
    if binding is None or (not binding.enabled and not allow_disabled):
        session.rollback()
        return False
    expected = config.allowlist.get(question.sender)
    if binding.sender_hash != config.digest("sender", question.sender) or (
        binding.user_id != expected
        if expected is not None
        # Outside the private allowlist only households that joined by themselves get replies.
        else not households.is_self_serve(session, binding.user_id)
    ):
        session.rollback()
        return False
    if expected is None:
        # The Meta client sends only to allowlisted numbers, or to one vouched for here: this
        # self-serve household's own number, matched to its binding just above.
        client.allow(question.sender)
    if question.provider_at < datetime.now(UTC) - timedelta(hours=24):
        session.rollback()
        return False
    kind = "audio" if media_id is not None else "interactive" if buttons or listing else "text"
    if reminder:
        kind = "reminder"  # a pilot due card after the reply, still once per inbound message
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
        if listing is not None:
            delivery.outbound_message_id = client.send_list(
                question.sender,
                text=text or "",
                button=listing.button,
                section=listing.section,
                rows=listing.rows,
            )
        elif buttons:
            delivery.outbound_message_id = client.send_buttons(
                question.sender, text=text or "", buttons=buttons
            )
        else:
            delivery.outbound_message_id = client.send(
                question.sender, text=text, media_id=media_id
            )
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
            household = session.execute(
                select(User.pilot, User.joined_via, User.consented_at, User.deleted_at).where(
                    User.id == binding.user_id
                )
            ).one_or_none()
            if household is None or household.deleted_at is not None:
                receipts.finish(session, receipt_id, error="disabled")
                return
            # Only an explicit database true enables the village pilot flows (contract);
            # households that joined by themselves get the same diary (signup contract).
            is_pilot = household.pilot is True
            self_serve = household.joined_via is not None
            diary = is_pilot or self_serve
            conversation = pilot.Conversation(
                session,
                settings,
                config,
                client,
                receipt,
                question,
                binding,
                send_reply,
                self_serve=self_serve,
                heard=written_language(question),
            )
            if question.command:
                if diary and question.command in {"en", "hi", "ml"} and not binding.consented_at:
                    # Choosing a language before agreeing shows the consent card in it.
                    receipts.finish(session, receipt_id, error=pilot.ask_consent(conversation))
                    return
                response = {
                    "stop": (
                        "FinBoy WhatsApp replies are disabled. Send START to enable them again."
                    ),
                    "start": (
                        "FinBoy ledger questions are enabled. Send en, hindi or ml "
                        "to choose a language. Send STOP to disable replies."
                    ),
                    "en": "English replies selected. Ask a question about your FinBoy ledger.",
                    "hi": "हिन्दी चुनी गई है। FinBoy के रिकॉर्ड के बारे में सवाल पूछें।",
                    "ml": "മലയാളം തിരഞ്ഞെടുത്തു. FinBoy രേഖകളെക്കുറിച്ച് ചോദിക്കാം.",
                    **(
                        {
                            "stop": conversation.words.STOP_REPLY,
                            "start": conversation.words.START_REPLY,
                            "en": conversation.words.LANGUAGE_CHOSEN,
                            "hi": conversation.words.LANGUAGE_CHOSEN,
                            "ml": conversation.words.LANGUAGE_CHOSEN,
                        }
                        if diary
                        else {}
                    ),
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
            # Signing in to the website: a login code, or a tap on its card (any household).
            code = login.read_code(question.text) if question.kind == "text" else None
            if code is not None:
                receipts.finish(session, receipt_id, error=signup.handle_code(conversation, code))
                return
            tapped = prompts.parse(question.button_id or "") if question.kind == "button" else None
            if tapped is not None and session.scalar(
                select(WhatsAppPrompt.purpose).where(
                    WhatsAppPrompt.id == tapped[0], WhatsAppPrompt.binding_id == binding.id
                )
            ) in {"web_login", "link"}:
                prompt = prompts.claim(session, binding, tapped[0])
                error = (
                    signup.tap(conversation, prompt, tapped[1])
                    if prompt is not None
                    else conversation.done(
                        conversation.send(conversation.words.EXPIRED), "prompt_expired"
                    )
                )
                receipts.finish(session, receipt_id, error=error)
                return
            if (
                self_serve
                and household.consented_at is None
                and signup.JOIN.match(question.text or "")
                and not households.signup_open(session, settings)
            ):
                receipts.finish(session, receipt_id, error=signup.join(conversation))
                return
            if self_serve and household.consented_at is not None and question.kind != "button":
                try:
                    usage.use(
                        session,
                        settings,
                        binding.user_id,
                        "voice" if question.kind == "audio" else "ai",
                    )
                except AccessError:
                    sent = conversation.send(conversation.words.USAGE_LIMIT)
                    receipts.finish(
                        session, receipt_id, error=conversation.done(sent, "usage_limit")
                    )
                    return
            if diary:
                receipts.finish(session, receipt_id, error=pilot.handle(conversation))
                return
            if question.kind == "button":
                # Only pilot households are ever sent buttons; acknowledge without acting.
                receipts.finish(session, receipt_id, error="prompt_expired")
                return
            if question.kind == "image":
                # End this read snapshot; the import pipeline commits through its own sessions.
                session.rollback()
                result = capture.capture_screenshot(
                    session.get_bind(), settings, client, question, binding.user_id
                )
                ok = send_reply(
                    session,
                    config,
                    client,
                    receipt,
                    question,
                    text=phone_text(capture.capture_reply(result, conversation.language)),
                )
                receipts.finish(
                    session,
                    receipt_id,
                    error=capture.RECEIPT_ERRORS.get(result.outcome)
                    or (None if ok else "provider_unavailable"),
                )
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
            except (ProviderUnavailable, MetaUnavailable, InvalidAudio) as exc:
                code = (
                    "invalid_audio"
                    if isinstance(exc, (InvalidMedia, InvalidAudio))
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
                }[conversation.language]
                session.rollback()
                send_reply(session, config, client, receipt, question, text=response)
                receipts.finish(session, receipt_id, error=code)
                return
            binding.last_language = answer.speech_language  # committed with the reply below
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
                except ProviderUnavailable, MetaUnavailable, InvalidAudio:
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
