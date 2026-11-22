"""Channel orchestration calls the shared assistant and speech service boundaries."""

import logging
import re
from asyncio import AbstractEventLoop
from datetime import UTC, datetime, timedelta
from time import perf_counter
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
from finboy.services.advisor import service as advisor
from finboy.services.assistant import service as assistant
from finboy.services.conversations import store
from finboy.services.speech import service as speech
from finboy.services.speech.media import InvalidAudio
from finboy.services.whatsapp import capture, documents, pilot, premium, prompts, receipts, signup
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
    spoken: str | None = None,
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
    # The words of a spoken reply are kept, not its audio (docs/conversation-round/contract.md).
    offered = listing.rows if listing is not None else buttons or []
    store.add_sent(
        session,
        config.messages,
        user_id=binding.user_id,
        kind=(
            "list"
            if listing is not None
            else "buttons"
            if buttons
            else "voice_reply"
            if media_id is not None
            else "text"
        ),
        text=spoken if media_id is not None else text,
        choices=[title for _, title in offered],
        outcome=delivery.state,
        receipt_id=receipt.id,
        delivery_id=delivery.id,
        language=binding.last_language,
    )
    session.commit()
    return delivery.state == "sent"


def process_question(
    factory: sessionmaker[Session],
    settings: Settings,
    config: ChannelConfig,
    receipt_id: UUID,
    question: InboundQuestion,
    *,
    typing_loop: AbstractEventLoop | None = None,
) -> None:
    started = perf_counter()
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
                select(
                    User.pilot,
                    User.joined_via,
                    User.consented_at,
                    User.deleted_at,
                    User.suspended_at,
                ).where(User.id == binding.user_id)
            ).one_or_none()
            # A suspended household is treated like a deleted one: recorded, never answered.
            if household is None or not households.active(household):
                receipts.finish(session, receipt_id, error="disabled")
                return
            # Only an explicit database true enables the village pilot flows (contract);
            # households that joined by themselves get the same diary (signup contract).
            is_pilot = household.pilot is True
            self_serve = household.joined_via is not None
            diary = is_pilot or self_serve
            tapped = prompts.parse(question.button_id or "") if question.kind == "button" else None
            login_button = tapped is not None and session.scalar(
                select(WhatsAppPrompt.purpose).where(
                    WhatsAppPrompt.id == tapped[0], WhatsAppPrompt.binding_id == binding.id
                )
            ) in {"web_login", "link"}
            if question.kind == "button" and not (diary or login_button):
                receipts.finish(session, receipt_id, error="prompt_expired")
                return
            if typing_loop is not None:
                client.start_typing(typing_loop, question.message_id)
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
                    # The language sticks (receipts.admit). The first message agrees and welcomes.
                    _, error = pilot.begin(conversation, welcome=True)
                    receipts.finish(session, receipt_id, error=error)
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
            if tapped is not None and login_button:
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
            if question.kind == "document":
                # A Google Pay statement PDF (docs/statement-round/contract.md), for every
                # household. A first message agrees, then the import runs. No AI is used.
                if diary and binding.consented_at is None:
                    keep, error = pilot.begin(conversation, welcome=False)
                    if not keep:
                        receipts.finish(session, receipt_id, error=error)
                        return
                if self_serve and not premium.allowed(conversation):
                    error = premium.refuse(conversation, "PREMIUM_STATEMENT")
                    receipts.finish(session, receipt_id, error=error)
                    return
                # End this read snapshot; the import commits through its own sessions.
                session.rollback()
                imported = documents.import_document(
                    session.get_bind(), settings, client, question, binding.user_id
                )
                # Pilot households use WhatsApp only, so they get the facts without a link.
                link = None if is_pilot else documents.reports_link(settings, imported.statement)
                ok = send_reply(
                    session,
                    config,
                    client,
                    receipt,
                    question,
                    text=phone_text(
                        documents.document_reply(imported, conversation.language, link=link)
                    ),
                )
                receipts.finish(
                    session,
                    receipt_id,
                    error=documents.RECEIPT_ERRORS.get(imported.outcome)
                    or (None if ok else "provider_unavailable"),
                )
                return
            if (
                self_serve
                and household.consented_at is not None
                and question.kind in premium.REPLIES
                and not premium.allowed(conversation)
            ):
                # Free plan: explain Premium before any audio or photo is downloaded or metered.
                error = premium.refuse(conversation, premium.REPLIES[question.kind])
                receipts.finish(session, receipt_id, error=error)
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
                    store.note_transcript(
                        session.get_bind(), receipt.id, text, transcript.detected_language
                    )
                if not 1 <= len(text.strip()) <= 2000:
                    raise ProviderUnavailable("invalid_audio")
                answer = (
                    advisor.advise(
                        session,
                        user_id=binding.user_id,
                        text=text,
                        display_style=preferred or "auto",
                        channel="whatsapp",
                        settings=settings,
                    )
                    if settings.advisor_enabled
                    else assistant.answer_question(
                        session,
                        user_id=binding.user_id,
                        text=text,
                        display_style=preferred or "auto",
                        settings=settings,
                    )
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
            words = pilot.WORDS[answer.display_language]
            response = pilot.with_sources(phone_text(answer.display_text), answer, words)
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
                    send_reply(
                        session,
                        config,
                        client,
                        receipt,
                        question,
                        media_id=media_id,
                        spoken=answer.speech_text,
                    )
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
        # Reply time per kind of message (text, audio, image, button), without its content.
        logger.info(
            "whatsapp.processed",
            extra={"stage": question.kind, "duration_ms": round((perf_counter() - started) * 1000)},
        )
        keep_media(factory, settings, receipt_id, client)


def keep_media(
    factory: sessionmaker[Session], settings: Settings, receipt_id: UUID, client: MetaClient
) -> None:
    """After the reply: the voice note or photo of a household that agreed goes to R2. Never
    raises: the reply has gone, and a failed copy only means the file isn't kept."""
    if not settings.conversation_log_enabled:
        return
    try:
        downloads = list(client.downloads)
        client.downloads.clear()
        if downloads:
            with factory() as session:
                store.keep_downloads(session, settings, receipt_id, downloads)
    except Exception:
        logger.warning("conversation.log_failed", extra={"stage": "media"})
