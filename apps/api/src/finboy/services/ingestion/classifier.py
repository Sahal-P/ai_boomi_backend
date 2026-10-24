import re

from finboy.services.ingestion.claims import clear_non_transaction, financial_claims
from finboy.services.ingestion.normalize import NormalizedMessage
from finboy.services.ingestion.types import Classification

BANK_DOMAINS = {"alerts.hdfcbank.test", "alerts.icicibank.test", "hdfcbank.net", "icicibank.com"}
MERCHANT_DOMAINS = {"amazon.test", "receipts.swiggy.test", "bills.local.test"}


def trusted_domain(domain: str) -> bool:
    return domain in BANK_DOMAINS | MERCHANT_DOMAINS


def classify(message: NormalizedMessage) -> Classification:
    text = message.text.lower()
    claims = financial_claims(message.text)
    if claims:
        claim = claims[0]
        meanings: dict[str, Classification] = {
            "salary": "salary_credit",
            "refund": "refund_notice",
            "reversal": "refund_notice",
            "emi_due": "emi_notice",
            "bill_due": "bill_notice",
        }
        if claim.event_type in meanings:
            return meanings[claim.event_type]
        if re.search(r"\border confirmation\b", claim.context, re.I):
            return "order_confirmation"
        if re.search(r"\b(?:invoice|receipt)\b", claim.context, re.I):
            return "merchant_receipt"
        if re.search(r"\bupi\b", claim.context, re.I):
            return "upi_alert"
        if re.search(r"\bcard\b", claim.context, re.I):
            return "card_alert"
        return "bank_alert" if message.sender_domain in BANK_DOMAINS else "unknown"
    if clear_non_transaction(text):
        return "promotional" if re.search(r"\b(?:promo|win|offer)\b", text) else "non_financial"
    score = 2 * trusted_domain(message.sender_domain)
    score += len(
        re.findall(
            r"\b(?:debited|credited|payment|invoice|bill|emi|refund|salary|upi|order)\b", text
        )
    )
    return "unknown" if score else "non_financial"
