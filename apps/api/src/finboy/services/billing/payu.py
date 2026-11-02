"""PayU India: Hosted Checkout forms, result hashes and the postservice API.

docs/subscription-round/contract.md. PayU's SHA-512 hashes, keyed by the merchant salt, prove who
wrote a form or a result. Only fixed outcome codes cross this boundary: the salt, hashes, bodies
and PayU's messages are never logged or returned.
"""

import hashlib
import hmac
import json
import re
import secrets
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from types import TracebackType
from typing import Literal, Self
from uuid import uuid4

import httpx

from finboy.core.config import Settings

CHECKOUT_URLS = {
    "test": "https://test.payu.in/_payment",
    "production": "https://secure.payu.in/_payment",
}
SERVICE_URLS = {
    "test": "https://test.payu.in/merchant/postservice.php?form=2",
    "production": "https://info.payu.in/merchant/postservice.php?form=2",
}
PRODUCT = "FinBoy Premium monthly"
# Households have no personal name; PayU needs one (at most 20 characters in test mode).
FIRST_NAME = "FinBoy"
UDFS = ("udf1", "udf2", "udf3", "udf4", "udf5")
TXNID = re.compile(r"fb[0-9a-f]{23}")
CODE = re.compile(r"[A-Za-z0-9_]{1,16}")
MODE = re.compile(r"[A-Z]{2,12}")
PAYU_ID = re.compile(r"[0-9]{1,32}")
MAX_RESPONSE_BYTES = 64 * 1024

Outcome = Literal["paid", "pending", "failed"]
MandateState = Literal["active", "paused", "ended", "unknown"]


class PayUUnavailable(Exception):
    """PayU could not be reached or answered unexpectedly; never carries PayU's text."""


def sha512(text: str) -> str:
    return hashlib.sha512(text.encode()).hexdigest()


def new_txnid() -> str:
    """25 characters, PayU's limit. PayU refuses a txnid that has already succeeded."""
    return "fb" + secrets.token_hex(12)[:23]


def rupees(minor: int) -> str:
    return f"{minor // 100}.{minor % 100:02d}"


def minor_units(text: str) -> int | None:
    """PayU's amount text ("299.00", "299") in paise, or None when it is not a plain amount."""
    match = re.fullmatch(r"([0-9]{1,9})(?:\.([0-9]{1,2}))?", text.strip())
    if match is None:
        return None
    return int(match[1]) * 100 + int((match[2] or "0").ljust(2, "0"))


def si_details(amount_minor: int, start: date, end: date) -> str:
    """The monthly mandate PayU registers; UPI always counts from the day of consent."""
    return json.dumps(
        {
            "billingAmount": rupees(amount_minor),
            "billingCurrency": "INR",
            "billingCycle": "MONTHLY",
            "billingInterval": 1,
            "paymentStartDate": start.isoformat(),
            "paymentEndDate": end.isoformat(),
            "remarks": "FinBoy Premium",
        },
        separators=(",", ":"),
    )


def request_hash(fields: Mapping[str, str], salt: str) -> str:
    """sha512(key|txnid|amount|productinfo|firstname|email|udf1..udf5||||||[si_details|]SALT)."""
    parts = [fields[name] for name in ("key", "txnid", "amount", "productinfo", "firstname")]
    parts += [fields["email"], *(fields.get(name, "") for name in UDFS), *[""] * 5]
    if "si_details" in fields:
        parts.append(fields["si_details"])
    return sha512("|".join([*parts, salt]))


def response_hash(fields: Mapping[str, str], salt: str) -> str:
    """The reverse hash on a result: [additional_charges|]SALT|status||||||udf5..udf1|...|key."""
    parts = [salt, fields.get("status", ""), *[""] * 5]
    parts += [fields.get(name, "") for name in reversed(UDFS)]
    parts += [
        fields.get(name, "")
        for name in ("email", "firstname", "productinfo", "amount", "txnid", "key")
    ]
    charges = fields.get("additional_charges", "")
    return sha512("|".join([charges, *parts] if charges else parts))


def authentic(fields: Mapping[str, str], salt: str) -> bool:
    supplied = fields.get("hash", "").strip().lower()
    return len(supplied) == 128 and hmac.compare_digest(supplied, response_hash(fields, salt))


def command_hash(key: str, command: str, var1: str, salt: str) -> str:
    return sha512(f"{key}|{command}|{var1}|{salt}")


@dataclass(frozen=True)
class Checkout:
    action: str
    fields: dict[str, str]


def checkout_form(
    settings: Settings,
    *,
    txnid: str,
    amount_minor: int,
    email: str,
    phone: str,
    mandate: tuple[date, date] | None = None,
    hindi: bool = False,
) -> Checkout:
    """The signed form the browser posts to PayU; `mandate` (from, until) offers AutoPay."""
    if not settings.payu_merchant_key or settings.payu_merchant_salt is None:
        raise PayUUnavailable
    back = settings.payu_return_url
    fields = {
        "key": settings.payu_merchant_key,
        "txnid": txnid,
        "amount": rupees(amount_minor),
        "productinfo": PRODUCT,
        "firstname": FIRST_NAME,
        "email": email,
        "phone": phone,
        "surl": back,
        "furl": back,
        "curl": back,
    }
    if mandate is not None:
        # "Pay and Subscribe": the person may register AutoPay on PayU's page, or just pay.
        fields |= {"si": "4", "api_version": "7", "si_details": si_details(amount_minor, *mandate)}
    if hindi:
        fields["display_lang"] = "Hindi"
    fields["hash"] = request_hash(fields, settings.payu_merchant_salt.get_secret_value())
    return Checkout(CHECKOUT_URLS[settings.payu_environment], fields)


@dataclass(frozen=True)
class Result:
    """What one payment's outcome says, reduced to the fields FinBoy keeps."""

    txnid: str
    outcome: Outcome
    amount_minor: int | None
    payu_id: str | None
    mode: str | None
    mandate: bool
    error_code: str | None


def _outcome(status: str) -> Outcome:
    status = status.strip().lower()
    if status in {"success", "captured"}:
        return "paid"
    if status in {"pending", "in progress", "in-progress", "initiated"}:
        return "pending"
    return "failed"


def _code(value: object) -> str | None:
    text = str(value).strip() if isinstance(value, (str, int)) else ""
    return text if CODE.fullmatch(text) and text not in {"E000", "1"} else None


def _clean(pattern: re.Pattern[str], value: object) -> str | None:
    text = value.strip() if isinstance(value, str) else ""
    return text if pattern.fullmatch(text) else None


def read_result(fields: Mapping[str, str]) -> Result:
    """A return or webhook payload, already checked with `authentic`."""
    outcome = _outcome(fields.get("status", ""))
    return Result(
        txnid=fields.get("txnid", ""),
        outcome=outcome,
        amount_minor=minor_units(fields.get("amount", "")),
        payu_id=_clean(PAYU_ID, fields.get("mihpayid")),
        mode=_clean(MODE, fields.get("mode")),
        mandate=outcome == "paid" and fields.get("payment_source", "").strip().lower() == "sist",
        error_code=_code(fields.get("error")),
    )


@dataclass(frozen=True)
class Charged:
    outcome: Outcome
    payu_id: str | None
    error_code: str | None


class PayUClient:
    """Bounded postservice calls; requests are signed with the salt, which is never sent."""

    def __init__(self, settings: Settings, *, transport: httpx.BaseTransport | None = None) -> None:
        if not settings.payu_merchant_key or settings.payu_merchant_salt is None:
            raise PayUUnavailable
        self.key = settings.payu_merchant_key
        self._salt = settings.payu_merchant_salt.get_secret_value()
        self.url = SERVICE_URLS[settings.payu_environment]
        self.client = httpx.Client(
            timeout=10, follow_redirects=False, transport=transport, trust_env=False
        )

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        _type: type[BaseException] | None,
        _value: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        self.client.close()

    def call(self, command: str, var1: str) -> dict[str, object]:
        data = {
            "key": self.key,
            "command": command,
            "var1": var1,
            "hash": command_hash(self.key, command, var1, self._salt),
        }
        try:
            response = self.client.post(self.url, data=data, headers={"Accept": "application/json"})
        except httpx.HTTPError:
            raise PayUUnavailable from None
        if response.status_code >= 300 or len(response.content) > MAX_RESPONSE_BYTES:
            raise PayUUnavailable
        try:
            body = response.json()
        except ValueError:
            raise PayUUnavailable from None
        if not isinstance(body, dict):
            raise PayUUnavailable
        return body

    def verify(self, txnids: Sequence[str]) -> dict[str, Result]:
        """verify_payment for up to 25 of our txnids; unknown ones are left out."""
        if not txnids:
            return {}
        body = self.call("verify_payment", "|".join(txnids[:25]))
        details = body.get("transaction_details")
        if not isinstance(details, dict):
            raise PayUUnavailable
        found: dict[str, Result] = {}
        for txnid in txnids[:25]:
            entry = details.get(txnid)
            status = entry.get("status") if isinstance(entry, dict) else None
            if not isinstance(status, str) or status.strip().lower() == "not found":
                continue
            amount = entry.get("amt") or entry.get("transaction_amount") or ""
            found[txnid] = Result(
                txnid=txnid,
                outcome=_outcome(status),
                amount_minor=minor_units(amount) if isinstance(amount, str) else None,
                payu_id=_clean(PAYU_ID, entry.get("mihpayid")),
                mode=_clean(MODE, entry.get("mode")),
                mandate=_outcome(status) == "paid"
                and str(entry.get("payment_source", "")).strip().lower() == "sist",
                error_code=_code(entry.get("error_code")),
            )
        return found

    def pre_debit(
        self,
        *,
        mandate: str,
        amount_minor: int,
        debit_on: date,
        invoice: str,
        sequence: int | None,
    ) -> str | None:
        """Notify the payer of a coming debit; None when PayU accepted it, else its short code."""
        var1: dict[str, object] = {
            "authpayuid": mandate,
            "requestId": uuid4().hex,
            "amount": rupees(amount_minor),
            "debitDate": debit_on.isoformat(),
            "invoiceDisplayNumber": invoice,
        }
        if sequence is not None:
            var1["mandateSeqNo"] = sequence
        body = self.call("pre_debit_SI", json.dumps(var1, separators=(",", ":")))
        status = body.get("status")
        return None if status in {1, "1"} else (_code(status) or "rejected")

    def charge(
        self, *, mandate: str, txnid: str, amount_minor: int, invoice: str, sequence: int | None
    ) -> Charged:
        """si_transaction: debit a registered mandate after its pre-debit notice."""
        var1: dict[str, object] = {
            "authpayuid": mandate,
            "invoiceDisplayNumber": invoice,
            "amount": rupees(amount_minor),
            "txnid": txnid,
        }
        if sequence is not None:
            var1["mandateSeqNo"] = sequence
        body = self.call("si_transaction", json.dumps(var1, separators=(",", ":")))
        details = body.get("details")
        entry = details.get(txnid) if isinstance(details, dict) else None
        if body.get("status") not in {1, "1"} or not isinstance(entry, dict):
            return Charged("failed", None, _code(body.get("status")) or "rejected")
        outcome = _outcome(str(entry.get("status", "")))
        return Charged(
            outcome,
            _clean(PAYU_ID, entry.get("payuid")),
            None if outcome == "paid" else "declined",
        )

    def mandate_state(self, mandate: str, kind: str) -> MandateState:
        """upi_mandate_status or check_mandate_status, reduced to what FinBoy acts on."""
        command = "upi_mandate_status" if kind == "upi" else "check_mandate_status"
        var1 = json.dumps({"authPayuId": mandate, "requestId": uuid4().hex}, separators=(",", ":"))
        status = self.call(command, var1).get("status")
        if not isinstance(status, str):
            return "unknown"
        status = status.strip().lower()
        if status == "active":
            return "active"
        if status == "paused":
            return "paused"
        return "ended" if status.isalpha() else "unknown"

    def revoke(self, mandate: str, kind: str) -> bool:
        """Cancel a mandate at the bank; True when PayU confirmed it."""
        if kind == "upi":
            command, field = "upi_mandate_revoke", "authPayuId"
        else:
            command, field = "mandate_revoke", "authpayuid"
        var1 = json.dumps({field: mandate, "requestId": uuid4().hex}, separators=(",", ":"))
        return self.call(command, var1).get("status") in {1, "1"}
