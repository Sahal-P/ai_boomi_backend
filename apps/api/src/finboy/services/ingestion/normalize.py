import hashlib
import re
from dataclasses import dataclass
from datetime import datetime
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr, parsedate_to_datetime
from html.parser import HTMLParser

MAX_TEXT = 12000
MAX_RAW = 2 * 1024 * 1024


class _HTMLText(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "head"}:
            self.hidden += 1
        if tag in {"p", "br", "div", "tr", "li"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "head"}:
            self.hidden = max(0, self.hidden - 1)
        if tag in {"p", "div", "td", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self.hidden:
            self.parts.append(data)


@dataclass(frozen=True)
class NormalizedMessage:
    sender_domain: str
    subject_sha256: str
    received_at: datetime | None
    text: str
    content_sha256: str


def minimize(text: str) -> str:
    """Retain financial values/dates; mask account, phone and long numeric identifiers."""
    text = re.sub(r"[\w.+-]+@[\w.-]+", "[address]", text)
    text = re.sub(
        r"(?:₹|Rs\.?|INR)\s*[\d,]+(?:\.\d{1,2})?|\d{5,}",
        lambda m: m[0] if not m[0].isdigit() else "X" * (len(m[0]) - 4) + m[0][-4:],
        text,
        flags=re.I,
    )
    return text


def normalize(raw: bytes, received_at: datetime | None = None) -> NormalizedMessage:
    if len(raw) > MAX_RAW:
        raise ValueError("message_too_large")
    message = BytesParser(policy=policy.default).parsebytes(raw)
    domain = parseaddr(str(message.get("From", "")))[1].rpartition("@")[2].lower()
    subject = str(message.get("Subject", ""))
    body = message.get_body(preferencelist=("plain", "html"))
    text = ""
    if body is not None and body.get_content_disposition() != "attachment":
        text = body.get_content()
        if body.get_content_type() == "text/html":
            parser = _HTMLText()
            parser.feed(text)
            text = "".join(parser.parts)
    lines: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if re.match(
            r"(?:On .+wrote:|-----Original Message|--$|Unsubscribe|Confidentiality)", line, re.I
        ):
            break
        if not line.startswith(">"):
            lines.append(re.sub(r"https?://\S+", "", line))
    text = minimize(subject + "\n" + "\n".join(lines))[:MAX_TEXT]
    text = re.sub(r"[ \t]+", " ", text)
    if received_at is None:
        try:
            received_at = parsedate_to_datetime(str(message.get("Date", "")))
        except ValueError, TypeError:
            received_at = None
    if received_at is not None and received_at.tzinfo is None:
        received_at = None
    return NormalizedMessage(
        domain,
        hashlib.sha256(subject.encode()).hexdigest(),
        received_at,
        text,
        hashlib.sha256(text.encode()).hexdigest(),
    )
