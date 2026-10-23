from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from hashlib import sha256
from pathlib import Path
from typing import Literal

from finboy.services.ingestion.pipeline import InboundMessage
from finboy.services.mail.security import MailError

MAX_FILES = 50
MAX_BYTES = 2 * 1024 * 1024
DEMO_DIRECTORY = Path(__file__).resolve().parents[4] / "fixtures" / "demo_mailbox"


def parse_eml(
    raw: bytes, *, source: Literal["eml_upload", "demo_mailbox"] = "eml_upload"
) -> InboundMessage:
    if not raw or len(raw) > MAX_BYTES:
        raise MailError("upload_limit")
    try:
        message = BytesParser(policy=policy.default).parsebytes(raw)
        if (
            message.defects
            or not message.get("From")
            or not message.get("Date")
            or any(getattr(value, "defects", ()) for value in message.values())
            or any(part.defects for part in message.walk())
        ):
            raise MailError("invalid_eml")
        parsedate_to_datetime(str(message["Date"]))
    except ValueError, TypeError, UnicodeError:
        raise MailError("invalid_eml") from None
    return InboundMessage(
        source=source, provider_message_id=sha256(raw).hexdigest(), raw_rfc822=raw
    )


def demo_messages() -> list[InboundMessage]:
    paths = sorted(DEMO_DIRECTORY.glob("*.eml"))
    if not paths:
        raise MailError("demo_unavailable")
    return [parse_eml(path.read_bytes(), source="demo_mailbox") for path in paths]
