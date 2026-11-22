"""The R2 adapter against botocore's own stubber: no network, no real bucket."""

from collections.abc import Iterator
from io import BytesIO
from uuid import UUID

import pytest
from botocore.response import StreamingBody
from botocore.stub import Stubber
from finboy.core.config import Settings
from finboy.services.conversations import r2

HOUSEHOLD = UUID("11111111-2222-3333-4444-555555555555")
MESSAGE = UUID("66666666-7777-8888-9999-000000000000")


def configured(settings: Settings, **changes: object) -> Settings:
    return Settings(
        **{
            **settings.model_dump(),
            "r2_account_id": "0" * 32,
            "r2_access_key_id": "synthetic-access",
            "r2_secret_access_key": "synthetic-secret",
            "r2_bucket": "synthetic-bucket",
            **changes,
        },
        _env_file=None,
    )


@pytest.fixture
def stubbed(settings: Settings) -> Iterator[tuple[Settings, Stubber]]:
    r2._clients.clear()
    ready = configured(settings)
    client, _ = r2._client(ready)
    with Stubber(client) as stubber:
        yield ready, stubber
        stubber.assert_no_pending_responses()
    r2._clients.clear()


def test_keys_live_in_one_folder_per_household_and_environment(settings: Settings) -> None:
    assert r2.key_for(configured(settings), HOUSEHOLD, MESSAGE, "audio/ogg") == (
        f"finboy-conversations-dev/{HOUSEHOLD}/{MESSAGE}.ogg"
    )
    production = configured(settings).model_copy(update={"environment": "production"})
    assert production.media_prefix == "finboy-conversations/"
    chosen = configured(settings, r2_prefix="finboy-staging/")
    assert r2.folder(chosen, HOUSEHOLD) == f"finboy-staging/{HOUSEHOLD}/"
    assert not r2.configured(settings)


def test_the_log_cannot_be_turned_on_without_r2(settings: Settings) -> None:
    with pytest.raises(ValueError, match="R2"):
        Settings(**{**settings.model_dump(), "conversation_log_enabled": True}, _env_file=None)
    with pytest.raises(ValueError):
        configured(settings, r2_prefix="../escape/")


def test_put_sends_the_file_with_its_type(stubbed: tuple[Settings, Stubber]) -> None:
    settings, stubber = stubbed
    key = r2.key_for(settings, HOUSEHOLD, MESSAGE, "image/jpeg")
    stubber.add_response(
        "put_object",
        {},
        {"Bucket": "synthetic-bucket", "Key": key, "Body": b"jpeg", "ContentType": "image/jpeg"},
    )
    r2.put(settings, key, b"jpeg", "image/jpeg")


def test_put_refuses_empty_oversized_or_unknown_files(settings: Settings) -> None:
    ready = configured(settings)
    for data, kind in ((b"", "audio/ogg"), (b"x" * (r2.MAX_BYTES + 1), "audio/ogg"), (b"x", "a/b")):
        with pytest.raises(r2.StoreUnavailable):
            r2.put(ready, "key", data, kind)


def test_provider_errors_never_carry_their_text(stubbed: tuple[Settings, Stubber]) -> None:
    settings, stubber = stubbed
    stubber.add_client_error("get_object", "AccessDenied", "synthetic provider detail", 403)
    with pytest.raises(r2.StoreUnavailable) as failed:
        r2.get(settings, "finboy-conversations-dev/x")
    assert "synthetic provider detail" not in repr(failed.value)


def test_get_reads_the_file(stubbed: tuple[Settings, Stubber]) -> None:
    settings, stubber = stubbed
    body = StreamingBody(BytesIO(b"OggS synthetic"), len(b"OggS synthetic"))
    stubber.add_response(
        "get_object", {"Body": body}, {"Bucket": "synthetic-bucket", "Key": "some/key.ogg"}
    )
    assert r2.get(settings, "some/key.ogg") == b"OggS synthetic"


def test_delete_folder_removes_every_page(stubbed: tuple[Settings, Stubber]) -> None:
    settings, stubber = stubbed
    folder = r2.folder(settings, HOUSEHOLD)
    stubber.add_response(
        "list_objects_v2",
        {
            "Contents": [{"Key": folder + "a.ogg"}],
            "IsTruncated": True,
            "NextContinuationToken": "t",
        },
        {"Bucket": "synthetic-bucket", "Prefix": folder},
    )
    stubber.add_response(
        "delete_objects",
        {},
        {
            "Bucket": "synthetic-bucket",
            "Delete": {"Objects": [{"Key": folder + "a.ogg"}], "Quiet": True},
        },
    )
    stubber.add_response(
        "list_objects_v2",
        {"Contents": [{"Key": folder + "b.jpg"}], "IsTruncated": False},
        {"Bucket": "synthetic-bucket", "Prefix": folder, "ContinuationToken": "t"},
    )
    stubber.add_response(
        "delete_objects",
        {"Errors": [{"Key": folder + "b.jpg", "Code": "InternalError"}]},
        {
            "Bucket": "synthetic-bucket",
            "Delete": {"Objects": [{"Key": folder + "b.jpg"}], "Quiet": True},
        },
    )
    with pytest.raises(r2.StoreUnavailable):
        r2.delete_folder(settings, HOUSEHOLD)  # a refused file is never reported as deleted
