"""The payer's email and phone, which PayU requires with every payment.

docs/subscription-round/contract.md. Typed once, validated against what PayU accepts, kept
Fernet-encrypted under `TOKEN_ENCRYPTION_KEY`, shown back masked, and erased with the account. A
linked WhatsApp number stands in for a phone the person has not typed.
"""

import re
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from finboy.core.config import Settings
from finboy.core.errors import AccessError
from finboy.db.models.billing import BillingProfile
from finboy.db.models.whatsapp import WhatsAppBinding
from finboy.services.mail.security import MailError, decrypt, encrypt

# PayU accepts letters, digits and - _ . @ in an email, at most 50 characters.
EMAIL = re.compile(r"[A-Za-z0-9._-]{1,64}@[A-Za-z0-9-]{1,63}(?:\.[A-Za-z0-9-]{1,63})+")


@dataclass(frozen=True)
class Contact:
    email: str | None
    phone: str | None
    phone_from_whatsapp: bool = False

    @property
    def masked_email(self) -> str | None:
        if self.email is None:
            return None
        local, _, domain = self.email.partition("@")
        return f"{local[:1]}•••@{domain}"

    @property
    def masked_phone(self) -> str | None:
        return None if self.phone is None else "•••• " + self.phone[-4:]


def clean_email(text: str) -> str | None:
    value = text.strip()
    if len(value) > 50 or ".." in value or not EMAIL.fullmatch(value):
        return None
    return value


def clean_phone(text: str) -> str | None:
    """An Indian mobile as 10 digits; other countries' numbers keep their country code."""
    digits = re.sub(r"[\s()+-]", "", text.strip())
    if not digits.isdigit():
        return None
    if len(digits) == 12 and digits.startswith("91"):
        digits = digits[2:]
    elif len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) == 10:
        return digits if digits[0] in "6789" else None
    return digits if 11 <= len(digits) <= 15 and not digits.startswith(("0", "91")) else None


def _key(settings: Settings) -> str:
    if settings.token_encryption_key is None:
        raise AccessError("billing_unavailable")
    return settings.token_encryption_key.get_secret_value()


def _open(key: str, value: bytes | None) -> str | None:
    if value is None:
        return None
    try:
        return decrypt(key, value)
    except MailError:
        return None


def stored(session: Session, settings: Settings, user_id: UUID) -> Contact:
    """What FinBoy can send PayU without asking: the saved contact, else the WhatsApp number."""
    if settings.token_encryption_key is None:
        return Contact(None, None)
    key = _key(settings)
    profile = session.get(BillingProfile, user_id)
    email = _open(key, profile.encrypted_email) if profile else None
    phone = _open(key, profile.encrypted_phone) if profile else None
    if phone is not None:
        return Contact(email, phone)
    sender = session.scalar(
        select(WhatsAppBinding.encrypted_sender)
        .where(WhatsAppBinding.user_id == user_id, WhatsAppBinding.encrypted_sender.is_not(None))
        .limit(1)
    )
    phone = clean_phone(_open(key, sender) or "") if sender is not None else None
    return Contact(email, phone, phone_from_whatsapp=phone is not None)


def save(
    session: Session, settings: Settings, user_id: UUID, *, email: str | None, phone: str | None
) -> None:
    """Validate what the person typed and keep it encrypted; blank fields keep what was saved."""
    email = email.strip() if email else None
    phone = phone.strip() if phone else None
    cleaned_email = clean_email(email) if email else None
    cleaned_phone = clean_phone(phone) if phone else None
    if (email and cleaned_email is None) or (phone and cleaned_phone is None):
        raise AccessError("invalid_contact")
    if cleaned_email is None and cleaned_phone is None:
        return
    key = _key(settings)
    profile = session.get(BillingProfile, user_id, with_for_update=True)
    if profile is None:
        profile = BillingProfile(user_id=user_id)
        session.add(profile)
    if cleaned_email is not None:
        profile.encrypted_email = encrypt(key, cleaned_email)
    if cleaned_phone is not None:
        profile.encrypted_phone = encrypt(key, cleaned_phone)
    session.flush()
