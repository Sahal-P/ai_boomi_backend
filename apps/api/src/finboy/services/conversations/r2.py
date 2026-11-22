"""Kept voice notes and photos in Cloudflare R2, through its S3 API (docs/conversation-round).

Every key is built here from IDs, as `<prefix><household id>/<message id>.<ext>`, never from
input, so one household's files always sit in one folder that erasure deletes whole. Failures
surface as `StoreUnavailable`, without the provider's text.
"""

import threading
from uuid import UUID

from botocore.client import BaseClient
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError
from botocore.session import get_session

from finboy.core.config import Settings

EXTENSIONS = {
    "audio/aac": "aac",
    "audio/amr": "amr",
    "audio/mpeg": "mp3",
    "audio/mp4": "m4a",
    "audio/ogg": "ogg",
    "image/jpeg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}
# The largest media FinBoy downloads from WhatsApp: photos up to 5 MB, voice notes up to 3 MB.
MAX_BYTES = 5 * 1024 * 1024

_clients: dict[tuple[str, str, str], BaseClient] = {}
_lock = threading.Lock()


class StoreUnavailable(Exception):
    """R2 refused or could not be reached; never carries the provider's message."""


def configured(settings: Settings) -> bool:
    return bool(
        settings.r2_account_id
        and settings.r2_access_key_id
        and settings.r2_secret_access_key
        and settings.r2_bucket
    )


def folder(settings: Settings, user_id: UUID) -> str:
    return f"{settings.media_prefix}{user_id}/"


def key_for(settings: Settings, user_id: UUID, message_id: UUID, content_type: str) -> str:
    return f"{folder(settings, user_id)}{message_id}.{EXTENSIONS[content_type]}"


def _client(settings: Settings) -> tuple[BaseClient, str]:
    if not configured(settings):
        raise StoreUnavailable
    account = settings.r2_account_id or ""
    access = settings.r2_access_key_id.get_secret_value() if settings.r2_access_key_id else ""
    secret = (
        settings.r2_secret_access_key.get_secret_value() if settings.r2_secret_access_key else ""
    )
    bucket = settings.r2_bucket or ""
    cache_key = (account, access, bucket)
    with _lock:
        client = _clients.get(cache_key)
        if client is None:
            # Botocore clients are thread-safe; one per process serves every reply worker.
            client = get_session().create_client(
                "s3",
                endpoint_url=f"https://{account}.r2.cloudflarestorage.com",
                region_name="auto",
                aws_access_key_id=access,
                aws_secret_access_key=secret,
                config=Config(
                    signature_version="s3v4",
                    retries={"max_attempts": 2},
                    connect_timeout=5,
                    read_timeout=15,
                ),
            )
            _clients[cache_key] = client
    return client, bucket


def put(settings: Settings, key: str, data: bytes, content_type: str) -> None:
    if not data or len(data) > MAX_BYTES or content_type not in EXTENSIONS:
        raise StoreUnavailable
    client, bucket = _client(settings)
    try:
        client.put_object(Bucket=bucket, Key=key, Body=data, ContentType=content_type)
    except BotoCoreError, ClientError:
        raise StoreUnavailable from None


def get(settings: Settings, key: str) -> bytes:
    client, bucket = _client(settings)
    try:
        response = client.get_object(Bucket=bucket, Key=key)
        body = response["Body"]
        try:
            data = body.read(MAX_BYTES + 1)
        finally:
            body.close()
    except BotoCoreError, ClientError:
        raise StoreUnavailable from None
    if len(data) > MAX_BYTES:
        raise StoreUnavailable
    return data


def delete(settings: Settings, key: str) -> None:
    """One file, like a feedback screenshot its household deleted."""
    client, bucket = _client(settings)
    try:
        client.delete_object(Bucket=bucket, Key=key)
    except BotoCoreError, ClientError:
        raise StoreUnavailable from None


def delete_folder(settings: Settings, user_id: UUID, prefix: str | None = None) -> int:
    """Every file in one household's folder, kept or orphaned by a failed write. `prefix` picks
    another FinBoy folder of the same bucket (feedback screenshots)."""
    client, bucket = _client(settings)
    removed = 0
    try:
        pages = client.get_paginator("list_objects_v2").paginate(
            Bucket=bucket, Prefix=f"{prefix}{user_id}/" if prefix else folder(settings, user_id)
        )
        for page in pages:
            keys = [{"Key": item["Key"]} for item in page.get("Contents", [])]
            if not keys:
                continue
            result = client.delete_objects(Bucket=bucket, Delete={"Objects": keys, "Quiet": True})
            if result.get("Errors"):
                raise StoreUnavailable
            removed += len(keys)
    except BotoCoreError, ClientError:
        raise StoreUnavailable from None
    return removed
