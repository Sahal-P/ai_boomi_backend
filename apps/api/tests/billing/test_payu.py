import hashlib
import json
from datetime import date
from urllib.parse import parse_qs

import httpx
import pytest
from finboy.core.config import Settings
from finboy.services.billing.payu import (
    CHECKOUT_URLS,
    TXNID,
    PayUClient,
    PayUUnavailable,
    authentic,
    checkout_form,
    command_hash,
    minor_units,
    new_txnid,
    read_result,
    request_hash,
    response_hash,
    si_details,
)
from pydantic import ValidationError

from .support import KEY, SALT, billing_settings

EMAIL = "someone@example.in"
TXN = "fb0123456789abcdef0123456"


def digest(text: str) -> str:
    return hashlib.sha512(text.encode()).hexdigest()


def result_fields(**overrides: str) -> dict[str, str]:
    fields = {
        "key": KEY,
        "txnid": TXN,
        "amount": "299.00",
        "productinfo": "FinBoy Premium monthly",
        "firstname": "FinBoy",
        "email": EMAIL,
        "status": "success",
        "mihpayid": "403993715531234567",
        "mode": "UPI",
        "error": "E000",
    }
    fields.update(overrides)
    fields.setdefault("hash", response_hash(fields, SALT))
    return fields


def test_request_hash_follows_payus_documented_order() -> None:
    fields = {
        "key": KEY,
        "txnid": TXN,
        "amount": "299.00",
        "productinfo": "FinBoy Premium monthly",
        "firstname": "FinBoy",
        "email": EMAIL,
    }
    # sha512(key|txnid|amount|productinfo|firstname|email|||||||||||SALT), as PayU documents.
    expected = digest(f"{KEY}|{TXN}|299.00|FinBoy Premium monthly|FinBoy|{EMAIL}|||||||||||{SALT}")
    assert request_hash(fields, SALT) == expected
    mandate = si_details(29900, date(2026, 12, 2), date(2031, 12, 2))
    fields["si_details"] = mandate
    expected = digest(
        f"{KEY}|{TXN}|299.00|FinBoy Premium monthly|FinBoy|{EMAIL}|||||||||||{mandate}|{SALT}"
    )
    assert request_hash(fields, SALT) == expected


def test_response_hash_is_the_documented_reverse_order() -> None:
    fields = result_fields()
    expected = digest(
        f"{SALT}|success|||||||||||{EMAIL}|FinBoy|FinBoy Premium monthly|299.00|{TXN}|{KEY}"
    )
    assert response_hash(fields, SALT) == expected
    charged = result_fields(additional_charges="5.90", hash="")
    expected = digest(
        f"5.90|{SALT}|success|||||||||||{EMAIL}|FinBoy|FinBoy Premium monthly|299.00|{TXN}|{KEY}"
    )
    assert response_hash(charged, SALT) == expected


def test_only_an_untouched_result_is_authentic() -> None:
    fields = result_fields()
    assert authentic(fields, SALT)
    assert authentic({**fields, "hash": fields["hash"].upper()}, SALT)
    assert not authentic({**fields, "amount": "1.00"}, SALT)
    assert not authentic({**fields, "status": "failure"}, SALT)
    assert not authentic({**fields, "hash": ""}, SALT)
    assert not authentic({k: v for k, v in fields.items() if k != "hash"}, SALT)
    assert not authentic(fields, "another-salt-value")


def test_read_result_keeps_only_categories_and_codes() -> None:
    paid = read_result(result_fields(payment_source="sist"))
    assert paid.outcome == "paid" and paid.mandate and paid.amount_minor == 29900
    assert paid.payu_id == "403993715531234567" and paid.mode == "UPI" and paid.error_code is None
    once = read_result(result_fields(payment_source="payu"))
    assert once.outcome == "paid" and not once.mandate
    failed = read_result(result_fields(status="failure", error="E308", mode="upi <b>"))
    assert failed.outcome == "failed" and failed.error_code == "E308" and failed.mode is None
    assert read_result(result_fields(status="pending")).outcome == "pending"
    # A mandate needs a successful payment, whatever the source says.
    assert not read_result(result_fields(status="failure", payment_source="sist")).mandate


@pytest.mark.parametrize(
    ("text", "minor"),
    [("299.00", 29900), ("299", 29900), ("299.5", 29950), ("0.01", 1), ("-1", None), ("1e3", None)],
)
def test_amounts(text: str, minor: int | None) -> None:
    assert minor_units(text) == minor


def test_txnids_fit_payus_limit() -> None:
    ids = {new_txnid() for _ in range(200)}
    assert len(ids) == 200
    assert all(len(value) == 25 and TXNID.fullmatch(value) for value in ids)


def test_checkout_form_signs_without_revealing_the_salt(billing: Settings) -> None:
    form = checkout_form(billing, txnid=TXN, amount_minor=29900, email=EMAIL, phone="9876543210")
    assert form.action == CHECKOUT_URLS["test"]
    assert form.fields["surl"] == form.fields["furl"] == "http://127.0.0.1:8071/api/v1/payu/return"
    assert SALT not in json.dumps(form.fields)
    assert "si" not in form.fields and "display_lang" not in form.fields
    assert form.fields["hash"] == request_hash(form.fields, SALT)
    autopay = checkout_form(
        billing,
        txnid=TXN,
        amount_minor=29900,
        email=EMAIL,
        phone="9876543210",
        mandate=(date(2026, 12, 2), date(2031, 12, 2)),
        hindi=True,
    )
    assert autopay.fields["si"] == "4" and autopay.fields["api_version"] == "7"
    assert json.loads(autopay.fields["si_details"]) == {
        "billingAmount": "299.00",
        "billingCurrency": "INR",
        "billingCycle": "MONTHLY",
        "billingInterval": 1,
        "paymentStartDate": "2026-12-02",
        "paymentEndDate": "2031-12-02",
        "remarks": "FinBoy Premium",
    }
    assert autopay.fields["display_lang"] == "Hindi"
    assert autopay.fields["hash"] == request_hash(autopay.fields, SALT)
    live = billing_settings(payu_environment="production")
    assert checkout_form(live, txnid=TXN, amount_minor=1, email=EMAIL, phone="1").action == (
        "https://secure.payu.in/_payment"
    )


def test_billing_settings_fail_closed() -> None:
    with pytest.raises(ValidationError):
        billing_settings(payu_merchant_salt="")
    with pytest.raises(ValidationError):
        billing_settings(api_public_url="https://finboy.example/api")
    with pytest.raises(ValidationError):
        billing_settings(api_public_url="https://a-very-long-api-host-name.finboy.example")
    with pytest.raises(ValidationError):
        billing_settings(token_encryption_key=None)
    production = {
        "environment": "production",
        "household_password_hash": "scrypt$" + "00" * 16 + "$" + "00" * 64,
        "web_session_key": billing_settings().token_encryption_key.get_secret_value(),  # type: ignore[union-attr]
        "cors_origins": ["https://finboy.io"],
        "web_app_url": "https://finboy.io",
        "api_public_url": "https://finboy.io",
    }
    with pytest.raises(ValidationError):
        billing_settings(**production, billing_launch_date="2026-11-10")  # still test PayU
    with pytest.raises(ValidationError):
        billing_settings(**production, payu_environment="production")  # no launch date
    ready = billing_settings(
        **production, payu_environment="production", billing_launch_date="2026-11-10"
    )
    assert ready.payu_return_url == "https://finboy.io/api/v1/payu/return"
    # Billing off needs none of it.
    assert not billing_settings(billing_enabled=False, payu_merchant_key=None).billing_enabled


class Recorder:
    def __init__(self, *bodies: object, status: int = 200) -> None:
        self.bodies = list(bodies)
        self.status = status
        self.requests: list[dict[str, str]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        form = {k: v[0] for k, v in parse_qs(request.content.decode()).items()}
        self.requests.append(form)
        body = self.bodies.pop(0)
        if isinstance(body, bytes):
            return httpx.Response(self.status, content=body)
        return httpx.Response(self.status, json=body)


def client(recorder: Recorder) -> PayUClient:
    return PayUClient(billing_settings(), transport=httpx.MockTransport(recorder))


def test_calls_are_signed_and_never_send_the_salt() -> None:
    recorder = Recorder({"status": 1, "msg": "ok", "transaction_details": {}})
    with client(recorder) as payu:
        assert payu.verify([TXN]) == {}
    sent = recorder.requests[0]
    assert sent["command"] == "verify_payment" and sent["var1"] == TXN
    assert sent["hash"] == command_hash(KEY, "verify_payment", TXN, SALT)
    assert SALT not in json.dumps(sent)


def test_verify_maps_statuses_and_skips_unknown_ids() -> None:
    other = "fb" + "1" * 23
    recorder = Recorder(
        {
            "status": 1,
            "transaction_details": {
                TXN: {"mihpayid": "999", "status": "success", "amt": "299.00", "mode": "CC"},
                other: {"mihpayid": "Not Found", "status": "Not Found"},
            },
        }
    )
    with client(recorder) as payu:
        found = payu.verify([TXN, other])
    assert list(found) == [TXN]
    assert found[TXN].outcome == "paid" and found[TXN].amount_minor == 29900
    assert found[TXN].mode == "CC" and found[TXN].payu_id == "999"


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(500, json={}),
        httpx.Response(200, content=b"<html>"),
        httpx.Response(200, json=["not", "a", "dict"]),
        httpx.Response(200, content=b"{" + b" " * 70000 + b"}"),
    ],
)
def test_unexpected_answers_are_unavailable(response: httpx.Response) -> None:
    payu = PayUClient(billing_settings(), transport=httpx.MockTransport(lambda _r: response))
    with pytest.raises(PayUUnavailable):
        payu.call("verify_payment", TXN)


def test_network_failures_are_unavailable() -> None:
    def broken(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom")

    payu = PayUClient(billing_settings(), transport=httpx.MockTransport(broken))
    with pytest.raises(PayUUnavailable):
        payu.call("verify_payment", TXN)


def test_pre_debit_and_charge() -> None:
    recorder = Recorder(
        {"status": 1, "action": "MANDATE_PRE_DEBIT"},
        {"status": "E9254", "message": "Predebit notification already sent"},
        {"status": 1, "details": {TXN: {"status": "pending", "payuid": "77"}}},
        {"status": 1, "details": {TXN: {"status": "captured", "payuid": "78"}}},
        {"status": 1, "details": {TXN: {"status": "failed", "field9": "Insufficient funds"}}},
        {"status": 0, "msg": "Invalid Hash."},
    )
    with client(recorder) as payu:
        args = {"mandate": "123", "amount_minor": 29900, "invoice": TXN, "sequence": 2}
        assert payu.pre_debit(debit_on=date(2026, 12, 2), **args) is None  # type: ignore[arg-type]
        assert payu.pre_debit(debit_on=date(2026, 12, 2), **args) == "E9254"  # type: ignore[arg-type]
        assert payu.charge(txnid=TXN, **args).outcome == "pending"  # type: ignore[arg-type]
        assert payu.charge(txnid=TXN, **args).payu_id == "78"  # type: ignore[arg-type]
        assert payu.charge(txnid=TXN, **args).outcome == "failed"  # type: ignore[arg-type]
        assert payu.charge(txnid=TXN, **args).error_code == "0"  # type: ignore[arg-type]
    notice = json.loads(recorder.requests[0]["var1"])
    assert notice["debitDate"] == "2026-12-02" and notice["mandateSeqNo"] == 2
    assert notice["amount"] == "299.00" and recorder.requests[0]["command"] == "pre_debit_SI"
    assert json.loads(recorder.requests[2]["var1"])["txnid"] == TXN


def test_mandate_state_and_revoke() -> None:
    recorder = Recorder(
        {"status": "active", "action": "MANDATE_STATUS"},
        {"status": "paused"},
        {"status": "revoked"},
        {"status": 0, "message": "Mandate entry not found"},
        {"status": 1, "action": "MANDATE_REVOKE"},
        {"status": 0, "message": "Mandate is not active"},
    )
    with client(recorder) as payu:
        assert payu.mandate_state("123", "upi") == "active"
        assert payu.mandate_state("123", "card") == "paused"
        assert payu.mandate_state("123", "upi") == "ended"
        assert payu.mandate_state("123", "upi") == "unknown"
        assert payu.revoke("123", "upi")
        assert not payu.revoke("123", "card")
    commands = [request["command"] for request in recorder.requests]
    assert commands == [
        "upi_mandate_status",
        "check_mandate_status",
        "upi_mandate_status",
        "upi_mandate_status",
        "upi_mandate_revoke",
        "mandate_revoke",
    ]
