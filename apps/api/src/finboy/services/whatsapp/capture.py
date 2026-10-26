"""Screenshots and pilot voice entries enter review through the shared import pipeline only."""

import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy import Engine, select
from sqlalchemy.orm import sessionmaker

from finboy.core.config import LOCAL_USER_ID, Settings
from finboy.core.languages import Language
from finboy.db.models.ledger import EmailSource, SourceEvent, Transaction
from finboy.db.models.mail import ImportRun
from finboy.services.assistant.language import money
from finboy.services.imports.runner import create_run, run_import
from finboy.services.ingestion import screenshot
from finboy.services.ingestion.pipeline import InboundMessage
from finboy.services.ingestion.types import Category
from finboy.services.mail.security import MailError
from finboy.services.whatsapp import statement
from finboy.services.whatsapp.events import InboundQuestion
from finboy.services.whatsapp.meta import InvalidMedia, MetaClient, MetaUnavailable

Outcome = Literal["saved", "already_recorded", "no_payment", "busy", "invalid_image", "unavailable"]
RECEIPT_ERRORS: dict[Outcome, str] = {
    "busy": "capture_busy",
    "invalid_image": "invalid_image",
    "unavailable": "capture_unavailable",
}


@dataclass(frozen=True)
class Capture:
    outcome: Outcome
    amount_minor: int | None = None
    merchant: str | None = field(default=None, repr=False)
    transaction_id: UUID | None = None


def capture_screenshot(
    engine: Engine,
    settings: Settings,
    client: MetaClient,
    question: InboundQuestion,
    user_id: UUID = LOCAL_USER_ID,
) -> Capture:
    try:
        image = client.download_image(question.media_id or "", question.mime_type or "")
        line = screenshot.read_payment(
            image.data, image.content_type, settings, question.provider_at
        )
    except InvalidMedia, screenshot.InvalidImage:
        return Capture("invalid_image")
    except MetaUnavailable, screenshot.CaptureUnavailable:
        return Capture("unavailable")
    if line is None:
        return Capture("no_payment")
    return _import_one(
        engine,
        settings,
        user_id=user_id,
        source="whatsapp_image",
        message_id=question.message_id,
        raw=screenshot.as_message(line, question.provider_at),
        received_at=question.provider_at,
    )


def record_voice(
    engine: Engine,
    settings: Settings,
    *,
    user_id: UUID,
    message_id: str,
    line: str,
    received_at: datetime,
    category: Category | None,
) -> Capture:
    """A pilot household's spoken payment line enters review exactly like a screenshot."""
    return _import_one(
        engine,
        settings,
        user_id=user_id,
        source="whatsapp_voice",
        message_id=message_id,
        raw=statement.as_message(line, received_at),
        received_at=received_at,
        category_hint=category,
        attempts=3,
    )


def _import_one(
    engine: Engine,
    settings: Settings,
    *,
    user_id: UUID,
    source: Literal["whatsapp_image", "whatsapp_voice"],
    message_id: str,
    raw: bytes,
    received_at: datetime,
    category_hint: Category | None = None,
    attempts: int = 1,
) -> Capture:
    factory = sessionmaker(engine, expire_on_commit=False)
    for attempt in range(attempts):
        try:
            with factory() as session:
                run_id = create_run(session, mode=source, user_id=user_id).id
            break
        except MailError:
            # Nothing is queued: the message is not retained, so the sender resends it.
            if attempt + 1 == attempts:
                return Capture("busy")
            time.sleep(1.5)
    run_import(
        engine,
        settings,
        run_id,
        [
            InboundMessage(
                source=source,
                provider_message_id=message_id,
                raw_rfc822=raw,
                received_at=received_at,
                category_hint=category_hint,
            )
        ],
    )
    with factory() as session:
        run = session.get(ImportRun, run_id)
        if run is None or run.status != "completed":
            return Capture("unavailable")
        row = session.execute(
            select(Transaction.id, Transaction.amount_minor, Transaction.merchant)
            .join(SourceEvent, SourceEvent.transaction_id == Transaction.id)
            .join(EmailSource, EmailSource.id == SourceEvent.email_source_id)
            .where(
                EmailSource.user_id == user_id,
                EmailSource.source == source,
                EmailSource.provider_message_id == message_id,
            )
            .order_by(SourceEvent.created_at, SourceEvent.id)
            .limit(1)
        ).first()
        created = bool(run.transactions_created)
    if row is None:
        return Capture("no_payment")
    return Capture(
        "saved" if created else "already_recorded", row.amount_minor, row.merchant, row.id
    )


def capture_reply(capture: Capture, language: Language | None) -> str:
    merchant = capture.merchant or ""
    payee = (
        merchant
        if merchant and "[address]" not in merchant and not merchant.lower().startswith("unknown")
        else None
    )
    amount = money(capture.amount_minor) if capture.amount_minor else ""
    # Screenshots may show money sent or received; do not invent a direction.
    phrase = f"{amount} · {payee}" if payee else amount
    return {
        "en": {
            "saved": f"Saved for review: {phrase}. It won't count in your totals until you "
            "confirm it in FinBoy.",
            "already_recorded": f"This payment ({phrase}) is already in FinBoy. The screenshot "
            "was added as extra evidence.",
            "no_payment": "I couldn't find a completed payment amount in that image. Send a "
            "screenshot of the payment confirmation screen.",
            "busy": "FinBoy is importing other records right now. Please send the screenshot "
            "again in a minute.",
            "invalid_image": "I couldn't read that image. Send a PNG or JPEG screenshot of the "
            "payment screen.",
            "unavailable": "Screenshot capture isn't available right now. Please try again later.",
        },
        "hi": {
            "saved": f"समीक्षा के लिए सहेजा गया: {phrase}। FinBoy में पुष्टि करने के बाद ही यह "
            "आपके कुल में गिना जाएगा।",
            "already_recorded": f"यह भुगतान ({phrase}) पहले से FinBoy में है। स्क्रीनशॉट को "
            "अतिरिक्त प्रमाण के रूप में जोड़ा गया।",
            "no_payment": "इस तस्वीर में पूरा हुआ भुगतान नहीं मिला। भुगतान की पुष्टि वाली स्क्रीन का "
            "स्क्रीनशॉट भेजें।",
            "busy": "FinBoy अभी दूसरे रिकॉर्ड इम्पोर्ट कर रहा है। एक मिनट बाद स्क्रीनशॉट फिर से भेजें।",
            "invalid_image": "यह तस्वीर पढ़ी नहीं जा सकी। भुगतान स्क्रीन का PNG या JPEG स्क्रीनशॉट भेजें।",
            "unavailable": "स्क्रीनशॉट से रिकॉर्ड बनाना अभी उपलब्ध नहीं है। बाद में फिर कोशिश करें।",
        },
        "ml": {
            "saved": f"അവലോകനത്തിനായി സേവ് ചെയ്തു: {phrase}. FinBoy-ൽ സ്ഥിരീകരിച്ചതിന് ശേഷം "
            "മാത്രമേ ഇത് നിങ്ങളുടെ ആകെ തുകയിൽ ഉൾപ്പെടുകയുള്ളൂ.",
            "already_recorded": f"ഈ പേയ്മെന്റ് ({phrase}) ഇതിനകം FinBoy-ൽ ഉണ്ട്. സ്ക്രീൻഷോട്ട് "
            "അധിക തെളിവായി ചേർത്തു.",
            "no_payment": "ഈ ചിത്രത്തിൽ പൂർത്തിയായ പേയ്മെന്റ് കണ്ടെത്താനായില്ല. പേയ്മെന്റ് "
            "സ്ഥിരീകരണ സ്ക്രീനിന്റെ സ്ക്രീൻഷോട്ട് അയയ്ക്കുക.",
            "busy": "FinBoy ഇപ്പോൾ മറ്റ് രേഖകൾ ഇംപോർട്ട് ചെയ്യുകയാണ്. ഒരു മിനിറ്റിന് ശേഷം "
            "സ്ക്രീൻഷോട്ട് വീണ്ടും അയയ്ക്കുക.",
            "invalid_image": "ഈ ചിത്രം വായിക്കാനായില്ല. പേയ്മെന്റ് സ്ക്രീനിന്റെ PNG അല്ലെങ്കിൽ "
            "JPEG സ്ക്രീൻഷോട്ട് അയയ്ക്കുക.",
            "unavailable": "സ്ക്രീൻഷോട്ടിൽ നിന്ന് രേഖ ഉണ്ടാക്കുന്നത് ഇപ്പോൾ ലഭ്യമല്ല. പിന്നീട് വീണ്ടും ശ്രമിക്കുക.",
        },
    }[language or "en"][capture.outcome]
