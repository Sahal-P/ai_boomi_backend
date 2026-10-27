"""Google ID tokens signed by a locally generated key; no request reaches Google."""

import datetime
import hashlib
import time

import httpx
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from finboy.core.errors import AccessError
from finboy.services.accounts.google import GoogleCerts, verify_id_token
from google.auth import crypt, jwt

CLIENT = "123456-abcdefgh.apps.googleusercontent.com"


def keypair() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "synthetic")])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(1)
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    private = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    return private, cert.public_bytes(serialization.Encoding.PEM).decode()


PRIVATE, CERT = keypair()


def token(**changes: object) -> str:
    claims = {
        "iss": "https://accounts.google.com",
        "aud": CLIENT,
        "sub": "112233445566",
        "email": "synthetic.person@example.test",
        "email_verified": True,
        "nonce": "browser-nonce",
        "iat": int(time.time()),
        "exp": int(time.time()) + 600,
    }
    claims.update(changes)
    signer = crypt.RSASigner.from_string(PRIVATE, key_id="k1")
    return jwt.encode(signer, claims).decode()


def certs() -> dict[str, str]:
    return {"k1": CERT}


def test_valid_token_keeps_only_a_subject_digest_and_masked_email() -> None:
    account = verify_id_token(token(), client_id=CLIENT, nonce="browser-nonce", certs=certs)
    assert account.subject_sha256 == hashlib.sha256(b"google:112233445566").hexdigest()
    assert account.email_masked == "s***@***.test"
    assert "synthetic.person" not in repr(account)


@pytest.mark.parametrize(
    ("changes", "client", "nonce"),
    [
        ({}, "999999-zzzzzzzz.apps.googleusercontent.com", "browser-nonce"),  # audience
        ({"iss": "https://evil.example.test"}, CLIENT, "browser-nonce"),  # issuer
        (
            {"exp": int(time.time()) - 3600, "iat": int(time.time()) - 7200},
            CLIENT,
            "browser-nonce",
        ),  # expired
        ({"email_verified": False}, CLIENT, "browser-nonce"),  # unverified email
        ({}, CLIENT, "another-browser"),  # nonce from a different browser
        ({"nonce": None}, CLIENT, "browser-nonce"),  # no nonce at all
        ({"sub": ""}, CLIENT, "browser-nonce"),  # no subject
    ],
)
def test_rejected_tokens_raise_one_fixed_code(changes, client, nonce) -> None:
    with pytest.raises(AccessError) as caught:
        verify_id_token(token(**changes), client_id=client, nonce=nonce, certs=certs)
    assert caught.value.code == "invalid_sign_in"


def test_forged_signature_and_garbage_are_rejected_without_quoting_input() -> None:
    _, other_cert = keypair()
    with pytest.raises(AccessError) as caught:
        verify_id_token(
            token(), client_id=CLIENT, nonce="browser-nonce", certs=lambda: {"k1": other_cert}
        )
    assert caught.value.code == "invalid_sign_in"
    with pytest.raises(AccessError) as caught:
        verify_id_token("SENSITIVE.not.a.token", client_id=CLIENT, nonce="x", certs=certs)
    assert "SENSITIVE" not in str(caught.value)


def test_certificates_are_cached_and_failures_are_a_fixed_code() -> None:
    calls = []

    def fetch() -> httpx.Response:
        calls.append(1)
        return httpx.Response(
            200,
            json={"k1": CERT},
            headers={"cache-control": "public, max-age=3600"},
            request=httpx.Request("GET", "https://certs.example.test"),
        )

    cache = GoogleCerts(fetch)
    assert cache() == {"k1": CERT} and cache() == {"k1": CERT}
    assert len(calls) == 1

    def broken() -> httpx.Response:
        raise httpx.ConnectError("SENSITIVE network detail")

    with pytest.raises(AccessError) as caught:
        GoogleCerts(broken)()
    assert caught.value.code == "sign_in_unavailable"
