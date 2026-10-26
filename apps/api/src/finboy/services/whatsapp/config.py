"""Private, fail-closed channel configuration. No identifiers belong in repr/logs."""

import hashlib
import hmac
import json
import re
from dataclasses import dataclass, field
from uuid import UUID

from finboy.core.config import LOCAL_USER_ID, Settings

# docs/pilot/contract.md: at most 10 hand-enrolled village pilot households besides the owner.
MAX_PILOT_HOUSEHOLDS = 10


class ChannelUnavailable(Exception):
    pass


@dataclass(frozen=True, repr=False)
class ChannelConfig:
    app_secret: str
    verify_token: str
    access_token: str
    phone_id: str
    account_id: str
    version: str
    hash_key: bytes
    allowlist: dict[str, UUID] = field(repr=False)
    timeout: float = 15
    max_body: int = 262144

    def digest(self, purpose: str, value: str | bytes) -> str:
        data = value.encode() if isinstance(value, str) else value
        return hmac.new(self.hash_key, purpose.encode() + b"\0" + data, hashlib.sha256).hexdigest()


def channel_config(settings: Settings) -> ChannelConfig:
    if not settings.whatsapp_enabled:
        raise ChannelUnavailable
    secrets = (
        settings.whatsapp_app_secret,
        settings.whatsapp_verify_token,
        settings.whatsapp_access_token,
        settings.whatsapp_phone_number_id,
        settings.whatsapp_business_account_id,
        settings.token_encryption_key,
        settings.whatsapp_sender_allowlist_json,
    )
    if not all(secrets) or settings.whatsapp_app_id != "953180210789448":
        raise ChannelUnavailable
    raw = [value.get_secret_value() for value in secrets if value is not None]
    version = settings.whatsapp_graph_api_version or ""
    if not re.fullmatch(r"v[0-9]{2,3}\.0", version):
        raise ChannelUnavailable
    try:
        approved = json.loads(raw[6])
        if not isinstance(approved, dict) or not 1 <= len(approved) <= 100:
            raise ValueError
        allowlist = {}
        for sender, user in approved.items():
            if not isinstance(sender, str) or not re.fullmatch(r"[0-9]{7,20}", sender):
                raise ValueError
            if not isinstance(user, str):
                raise ValueError
            # Non-owner households must also be enrolled pilots; admission checks the database.
            allowlist[sender] = UUID(user)
        if len(set(allowlist.values()) - {LOCAL_USER_ID}) > MAX_PILOT_HOUSEHOLDS:
            raise ValueError
        if not all(re.fullmatch(r"[0-9]{5,32}", item) for item in raw[3:5]):
            raise ValueError
    except ValueError, TypeError:
        raise ChannelUnavailable from None
    return ChannelConfig(
        *raw[:5],
        version,
        raw[5].encode(),
        allowlist,
        timeout=settings.whatsapp_timeout_seconds,
        max_body=settings.whatsapp_max_webhook_bytes,
    )
