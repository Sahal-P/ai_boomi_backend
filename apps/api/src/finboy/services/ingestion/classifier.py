import re

from finboy.services.ingestion.normalize import NormalizedMessage
from finboy.services.ingestion.types import Classification

BANK_DOMAINS = {"alerts.hdfcbank.test", "alerts.icicibank.test", "hdfcbank.net", "icicibank.com"}
MERCHANT_DOMAINS = {"amazon.test", "receipts.swiggy.test", "bills.local.test"}


def trusted_domain(domain: str) -> bool:
    return domain in BANK_DOMAINS | MERCHANT_DOMAINS


def classify(message: NormalizedMessage) -> Classification:
    text = message.text.lower()
    negative = len(re.findall(r"\b(?:promo|win|offer|newsletter|otp|one.time.password)\b", text))
    if negative:
        return "promotional" if re.search(r"\b(?:promo|win|offer)\b", text) else "non_financial"
    score = 2 * trusted_domain(message.sender_domain)
    score += len(
        re.findall(
            r"\b(?:debited|credited|payment|invoice|bill|emi|refund|salary|upi|order)\b", text
        )
    )
    if score < 2:
        return "unknown" if score else "non_financial"
    patterns: tuple[tuple[str, Classification], ...] = (
        (r"\bsalary\b", "salary_credit"),
        (r"\b(?:refund|reversal|reversed)\b", "refund_notice"),
        (r"\bemi\b.*\bdue\b", "emi_notice"),
        (r"\b(?:bill|amount)\b.*\bdue\b", "bill_notice"),
        (r"\border confirmation\b", "order_confirmation"),
        (r"\b(?:invoice|receipt)\b", "merchant_receipt"),
        (r"\bupi\b", "upi_alert"),
        (r"\bcard\b", "card_alert"),
    )
    for pattern, label in patterns:
        if re.search(pattern, text, re.S):
            return label
    return "bank_alert" if message.sender_domain in BANK_DOMAINS else "unknown"
