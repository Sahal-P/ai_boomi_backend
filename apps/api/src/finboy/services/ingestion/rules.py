import re
from datetime import datetime
from zoneinfo import ZoneInfo

from finboy.services.ingestion.amounts import AMOUNT_PATTERN, parse_amount
from finboy.services.ingestion.normalize import NormalizedMessage
from finboy.services.ingestion.types import Event, EventType, Extraction

IST = ZoneInfo("Asia/Kolkata")
PATTERNS = {
    "amount_minor": re.compile(AMOUNT_PATTERN, re.I),
    "merchant": re.compile(
        r"(?:at|to|from|Merchant:|Biller:)\s+(?P<merchant>[^;\n]+?)(?=\s+(?:on|via|for)\b|[;\n]|$)",
        re.I,
    ),
    "account_last4": re.compile(r"(?:XX|ending\s+|\*{2,})(?P<account_last4>\d{4})\b", re.I),
    "occurred_at": re.compile(
        r"(?:on|Date:)\s*(?P<date>\d{2}-\d{2}-\d{2,4})(?:\s+(?P<time>\d{2}:\d{2}))?", re.I
    ),
    "reference_id": re.compile(
        r"(?:UTR|Ref(?:erence)?|Order ID|Invoice ID)\s*[:#]\s*(?P<reference_id>[A-Z0-9-]+)", re.I
    ),
    "due_date": re.compile(r"\bdue(?: date)?[: ]+\s*(?P<due_date>\d{2}-\d{2}-\d{2,4})", re.I),
    "payment_instrument": re.compile(r"\b(?P<payment_instrument>UPI|NEFT|IMPS|card|NACH)\b", re.I),
}


def _date(value: str) -> datetime:
    return datetime.strptime(value, "%d-%m-%Y" if len(value) == 10 else "%d-%m-%y").replace(
        tzinfo=IST
    )


def extract_rules(message: NormalizedMessage) -> Extraction:
    text = message.text
    # A request to modify the ledger is not a notification of a financial event.
    if re.search(r"ignore (?:all )?(?:previous )?instructions|record .*credit", text, re.I):
        return Extraction(not_transaction=True)
    event_type: EventType
    if re.search(r"\b(?:failed|declined|unsuccessful)\b", text, re.I):
        event_type = "failed"
    elif re.search(r"\b(?:reversal|reversed)\b", text, re.I):
        event_type = "reversal"
    elif re.search(r"\brefund\b", text, re.I):
        event_type = "refund"
    elif re.search(r"\bemi\b.*\bdue\b", text, re.I | re.S):
        event_type = "emi_due"
    elif re.search(r"\bbill\b.*\bdue\b", text, re.I | re.S):
        event_type = "bill_due"
    elif re.search(r"\bcredit.card bill payment\b", text, re.I):
        event_type = "transfer"
    elif re.search(r"\bsalary\b.*\bcredited\b", text, re.I | re.S):
        event_type = "salary"
    elif re.search(r"\b(?:SIP|investment)\b.*\b(?:debited|paid)\b", text, re.I | re.S):
        event_type = "investment"
    elif re.search(r"\b(?:debited|paid|charged|order confirmation|invoice|receipt)\b", text, re.I):
        event_type = "debit"
    elif re.search(r"\bcredited\b", text, re.I):
        event_type = "credit"
    else:
        return Extraction()
    matches = {field: pattern.search(text) for field, pattern in PATTERNS.items()}
    amount = matches["amount_minor"]
    if amount is None:
        return Extraction()
    event = Event(event_type=event_type, amount_minor=parse_amount(amount[0]))
    event.evidence = {field: match[0][:80] for field, match in matches.items() if match}
    for field in ("merchant", "reference_id", "account_last4", "payment_instrument"):
        match = matches[field]
        if match:
            value = match[field].strip()
            limit = {
                "merchant": 160,
                "reference_id": 128,
                "account_last4": 4,
                "payment_instrument": 32,
            }[field]
            if len(value) > limit:
                event.evidence.pop(field, None)
                continue
            setattr(event, field, value)
    when = matches["occurred_at"]
    if when:
        try:
            event.occurred_at = _date(when["date"])
            if when["time"]:
                hour, minute = map(int, when["time"].split(":"))
                event.occurred_at = event.occurred_at.replace(hour=hour, minute=minute)
        except ValueError:
            event.evidence.pop("occurred_at", None)
    due = matches["due_date"]
    if due:
        try:
            event.due_date = _date(due["due_date"]).date()
        except ValueError:
            event.evidence.pop("due_date", None)
    event.payment_proof = bool(
        re.search(
            r"\b(?:debited|credited|charged|payment received|paid successfully)\b", text, re.I
        )
    )
    event.evidence["event_type"] = next(
        (
            line[:80]
            for line in text.splitlines()
            if re.search(r"debited|credited|due|failed|refund|reversed", line, re.I)
        ),
        text[:80],
    )
    if event.payment_proof:
        event.evidence["payment_proof"] = event.evidence["event_type"]
    event.field_confidence = dict.fromkeys(event.evidence, 1.0)
    event.rule_fields = list(event.evidence)
    return Extraction(events=[event])
