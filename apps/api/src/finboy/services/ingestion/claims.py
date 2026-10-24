"""Admit local financial assertions, not unrelated monetary text or global keywords."""

import re
from dataclasses import dataclass

from finboy.services.ingestion.amounts import AMOUNT_PATTERN, parse_amount
from finboy.services.ingestion.types import EventType

POLICY_VERSION = "claims-v1"
MODEL_CONFLICT = "model_non_transaction"

# Specific meanings precede general settlement. Each match still needs its own amount.
SIGNALS: tuple[tuple[EventType, str], ...] = (
    (
        "failed",
        r"\b(?:(?:payment|transaction)\b[^;\n!?]{0,80}?"
        r"(?:failed|declined|was unsuccessful)|declined)\b",
    ),
    ("reversal", r"\b(?:reversed|reversal)\b"),
    ("refund", r"\brefund(?:ed)?\b(?!\s+(?:policy|policies|request|eligib\w*|specialist))"),
    ("emi_due", r"\bemi\b[^;\n!?]{0,100}\bdue\b"),
    ("bill_due", r"\bbill\b[^;\n!?]{0,100}\bdue\b"),
    ("transfer", r"\bcredit.card bill payment\b[^;\n!?]{0,60}\b(?:debited|paid)\b"),
    ("salary", r"\bsalary\b[^;\n!?]{0,60}\bcredited\b"),
    ("investment", r"\b(?:sip|investment)\b[^;\n!?]{0,60}\b(?:debited|paid)\b"),
    ("debit", r"\b(?:debited|charged|paid)\b(?!\s+(?:time\s+off|vacation|leave|training|plans?))"),
    ("credit", r"\b(?:credited|payment received)\b"),
    (
        "debit",
        r"\b(?:order\s+confirmation|confirms\s+(?:the\s+|your\s+)?order|invoice|receipt)\b(?!\s+id\b)",
    ),
    ("debit", r"\bdebit\s+(?:for|of)\b"),
    ("credit", r"\bcredit\s+(?:for|of)\b"),
)
_SIGNALS = tuple((kind, re.compile(pattern, re.I)) for kind, pattern in SIGNALS)
_AMOUNT = re.compile(AMOUNT_PATTERN, re.I)
_SEPARATOR = re.compile(
    r"[;\n]+|(?<=[.!?])\s+(?=[A-Z])|,\s*"
    r"(?=(?i:invoice|receipt|(?:your\s+)?payment|debited|credited|refund|reversed|available\s+balance)\b)"
)
_PROOF = re.compile(r"\b(?:debited|credited|charged|payment received|paid successfully)\b", re.I)
_NON_ASSERTION = re.compile(
    r"\b(?:if|will|would|may\s+(?:be|have|get|qualify|receive|earn|pay|credit|debit)|"
    r"might|could|example|sample|calculator|illustration|pre.approved|prospective|hiring|"
    r"vacancy|careers?|jobs?\s+(?:at|available)|(?:developer|engineer)\s+jobs|apply|learn|course|get|earn|"
    r"need|eligible|eligibility|referral|send|can|scheduled)\b",
    re.I,
)
_NEGATED = re.compile(
    r"\b(?:not|never|no)(?:\s+(?:been|be|yet|actually|successfully|has|was|is)){0,4}$", re.I
)
_NON_EVENT_AMOUNT = re.compile(
    r"\b(?:balance|credit\s+limit|available\s+credit|mrp|course\s+price|list\s+price|"
    r"advertised\s+(?:salary|price)|salary\s+range)\s*(?:is|of|:|=)?\s*$",
    re.I,
)
_COMPENSATION = re.compile(
    r"\b(?:per\s+(?:annum|year|month|hour)|a\s+year|annually|lpa|after\s+joining|"
    r"credited\s+(?:monthly|weekly|annually))\b",
    re.I,
)
_NON_EVENT_SUFFIX = re.compile(
    r"\b(?:time\s+off|paid\s+vacation|paid\s+training|paid\s+plans?)\b", re.I
)
_METADATA = re.compile(
    r"^(?:merchant|biller|date|on\b|at\b|to\b|from\b|via\b|ref(?:erence)?|utr|"
    r"order\s+id|invoice\s+id|xx\d|ending\b|a/c\b|account\b|card\b|nach\b|"
    r"this confirms the order|not settlement)",
    re.I,
)


@dataclass(frozen=True)
class FinancialClaim:
    event_type: EventType
    amount_minor: int
    amount_evidence: str
    event_evidence: str
    context: str
    payment_proof: bool
    independent: bool
    payment_evidence: str | None


def _parts(text: str) -> list[tuple[int, int]]:
    parts = []
    start = 0
    for match in _SEPARATOR.finditer(text):
        if text[start : match.start()].strip():
            parts.append((start, match.start()))
        start = match.end()
    if text[start:].strip():
        parts.append((start, len(text)))
    return parts


def _context(text: str, parts: list[tuple[int, int]], left: int, right: int) -> str:
    end = parts[right][1]
    for start, stop in parts[right + 1 : right + 9]:
        if not _METADATA.search(text[start:stop].strip()) or _AMOUNT.search(text[start:stop]):
            break
        end = stop
    return text[parts[left][0] : end].strip()


def _eligible_pair(scope: str, signal: re.Match[str], amount: re.Match[str]) -> bool:
    before_signal = scope[: signal.start()].rstrip()
    # Negation and future/conditional language before the assertion do not prove settlement.
    if (
        _NEGATED.search(before_signal)
        or _NON_ASSERTION.search(before_signal)
        or _NON_ASSERTION.search(signal[0])
        or re.search(r"\bnot\b", signal[0], re.I)
    ):
        return False
    if _NON_EVENT_SUFFIX.search(signal[0]):
        return False
    between = scope[signal.end() : amount.start()] if signal.end() <= amount.start() else ""
    if _NON_ASSERTION.search(between) or re.search(r"\bnot\b", between, re.I):
        return False
    if _COMPENSATION.search(scope) and re.search(
        r"\b(?:salary|compensation|package|ctc)\b", scope, re.I
    ):
        return False
    if re.search(r"\b(?:download|generate|sample|example)\b", before_signal[-50:], re.I):
        return False
    if re.search(r"\b(?:refund|receipt|invoice)\s+(?:policy|template|download)\b", scope, re.I):
        return False
    low, high = sorted((signal.start(), amount.start()))
    if high - low > 140:
        return False
    # Another amount between the verb and this amount is a different claim, not evidence.
    if any(low < other.start() < high for other in _AMOUNT.finditer(scope)):
        return False
    previous_amount = max(
        (m.end() for m in _AMOUNT.finditer(scope) if m.end() <= amount.start()), default=0
    )
    if _NON_EVENT_AMOUNT.search(scope[max(previous_amount, amount.start() - 60) : amount.start()]):
        return False
    # A negation may sit after the amount but before the verb: INR 799 was not paid.
    return _NEGATED.search(scope[max(0, signal.start() - 45) : signal.start()].rstrip()) is None


def financial_claims(text: str) -> list[FinancialClaim]:
    """Bound claims to one clause, or a short adjacent multiline assertion."""
    parts = _parts(text)
    first_amount = _AMOUNT.search(text)
    if first_amount:
        prefix = text[: first_amount.start()]
        heading = re.search(
            r"\b(?:example|sample|tutorial|calculator|job\s+alerts?|jobs?\s+at|"
            r"(?:developer|engineer)\s+jobs|vacancy|hiring|careers?)\b",
            prefix,
            re.I,
        )
        assertions = [m.start() for _, pattern in _SIGNALS for m in pattern.finditer(prefix)]
        if heading and (not assertions or heading.start() < min(assertions)):
            return []
    claims: dict[tuple[int, int], FinancialClaim] = {}
    for index, (start, end) in enumerate(parts):
        if not _AMOUNT.search(text[start:end]):
            continue
        # Prefer the amount's own clause; preceding lines can supply 'Debited\nINR ...'.
        for left in range(index, max(-1, index - 3), -1):
            scope = text[parts[left][0] : end]
            if len(scope) > 600:
                break
            for amount in _AMOUNT.finditer(scope):
                position = (parts[left][0] + amount.start(), parts[left][0] + amount.end())
                if position[0] < start or position in claims:
                    continue
                for kind, pattern in _SIGNALS:
                    signal = next(
                        (m for m in pattern.finditer(scope) if _eligible_pair(scope, m, amount)),
                        None,
                    )
                    if signal is None:
                        continue
                    # Keep metadata for field extraction, but proof comes from this claim only.
                    proof_match = next(
                        (m for m in _PROOF.finditer(scope) if _eligible_pair(scope, m, amount)),
                        None,
                    )
                    proof = (
                        kind not in {"failed", "bill_due", "emi_due"} and proof_match is not None
                    )
                    context = _context(text, parts, left, index)
                    personal_anchor = bool(
                        re.search(
                            r"\b(?:UTR|Ref(?:erence)?)\s*[:#]\s*\S+|"
                            r"\b(?:XX\d{4}|ending\s+\d{4})\b",
                            context,
                            re.I,
                        )
                    )
                    independent = (proof and personal_anchor) or (
                        kind in {"bill_due", "emi_due"}
                        and bool(re.search(r"\b(?:Biller:|Ref:|UTR:)\s*\S+", context, re.I))
                        and bool(
                            re.search(r"\bdue(?: date)?[: ]+\s*\d{2}-\d{2}-\d{2,4}\b", scope, re.I)
                        )
                    )
                    claims[position] = FinancialClaim(
                        kind,
                        parse_amount(amount[0]),
                        amount[0],
                        signal[0][:80],
                        context,
                        proof,
                        independent,
                        proof_match[0] if proof and proof_match else None,
                    )
                    break
    return list(claims.values())[:8]


def event_signal(snippet: str, event_type: EventType) -> bool:
    """A verbatim quote must actually support its declared direction/meaning."""
    if snippet.casefold().strip() == event_type and event_type in {"debit", "credit"}:
        return True
    return any(kind == event_type and pattern.search(snippet) for kind, pattern in _SIGNALS)


def clear_non_transaction(text: str) -> bool:
    """Only called when there is no independent local financial claim."""
    return bool(
        re.search(
            r"\b(?:jobs?|vacancy|hiring|careers?|salary|compensation|newsletter|otp|offer|promo|"
            r"balance|credit(?:\s+card)?\s+limit|available\s+credit|refund\s+policy|"
            r"calculator|sample|example|price|cashback|paid\s+time\s+off|eligible|"
            r"referral|need|request)\b",
            text,
            re.I,
        )
    ) or bool(
        re.search(
            r"\b(?:not|never)\b.*\b(?:paid|debited|credited|charged|due)\b|"
            r"\b(?:get paid|(?:send|issue|request) an invoice)\b",
            text,
            re.I,
        )
    )
