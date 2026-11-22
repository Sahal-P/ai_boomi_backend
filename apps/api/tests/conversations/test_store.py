"""The message log's rules without a database: masking, the gate, files after the reply, and
removal that never leaves a file behind (docs/conversation-round/contract.md)."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from finboy.core.config import Settings
from finboy.core.errors import AccessError
from finboy.db.models.conversations import ConversationMessage
from finboy.services.conversations import r2, store
from finboy.services.whatsapp import processor
from finboy.services.whatsapp.events import InboundQuestion
from finboy.services.whatsapp.meta import DownloadedMedia
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

NOW = datetime(2026, 11, 22, 9, 30, tzinfo=UTC)
PROMPT = "0123456789abcdef0123456789abcdef"


@pytest.fixture
def kept(settings: Settings) -> Settings:
    return Settings(
        **{
            **settings.model_dump(),
            "conversation_log_enabled": True,
            "r2_account_id": "0" * 32,
            "r2_access_key_id": "synthetic-access",
            "r2_secret_access_key": "synthetic-secret",
            "r2_bucket": "synthetic-bucket",
        },
        _env_file=None,
    )


def standing(kept_from: datetime | None = NOW, **changes: object) -> SimpleNamespace:
    values = {"messages_kept_from": kept_from, "deleted_at": None, "suspended_at": None}
    values.update(changes)
    return SimpleNamespace(**values)


def session_for(row: SimpleNamespace | None) -> MagicMock:
    session = MagicMock(spec=Session)
    session.execute.return_value.one_or_none.return_value = row
    return session


def added(session: MagicMock) -> ConversationMessage:
    (row,), _ = session.add.call_args
    assert isinstance(row, ConversationMessage)
    return row


def question(kind: str = "text", **changes: object) -> InboundQuestion:
    values: dict[str, object] = {
        "message_id": "wamid.synthetic",
        "sender": "919000000001",
        "provider_at": NOW,
        "kind": kind,
    }
    values.update(changes)
    return InboundQuestion(**values)  # type: ignore[arg-type]


def test_clean_masks_identifiers_and_keeps_the_words() -> None:
    assert store.clean("chai 20, auto 50 to Ramesh") == "chai 20, auto 50 to Ramesh"
    assert store.clean("ABCD-EFGH") == "[login code]"
    assert store.clean("paid 500 to ramesh.k@okhdfcbank") == "paid 500 to [UPI ID]"
    assert store.clean("mail me at someone@example.com") == "mail me at someone@example.com"
    masked = store.clean("card 4111111111111111 and a/c XX1234 for ₹4,56,000")
    assert masked is not None
    assert "4111111111111111" not in masked and "XX1234" not in masked and "₹4,56,000" in masked
    assert store.clean("   ") is None and store.clean(None) is None
    assert len(store.clean("x" * 5000) or "") == store.LIMIT


@pytest.mark.parametrize(
    "row",
    [
        None,
        standing(None),
        standing(deleted_at=NOW),
        standing(suspended_at=NOW),
    ],
)
def test_only_an_active_household_that_agreed_is_kept(row: SimpleNamespace | None) -> None:
    assert store.kept_from(session_for(row), True, uuid4()) is None


def test_nothing_is_read_while_the_flag_is_off() -> None:
    session = session_for(standing())
    assert store.kept_from(session, False, uuid4()) is None
    session.execute.assert_not_called()
    assert store.kept_from(session_for(standing()), True, uuid4()) == NOW


def test_a_household_that_did_not_agree_adds_nothing() -> None:
    session = session_for(standing(None))
    store.add_inbound(session, True, user_id=uuid4(), receipt_id=uuid4(), question=question())
    store.add_sent(session, True, user_id=uuid4(), kind="text", text="Hi", outcome="sent")
    session.add.assert_not_called()


@pytest.mark.parametrize(
    ("kind", "changes", "expected"),
    [
        ("text", {"text": "chai 20"}, ("text", "chai 20", [])),
        ("text", {"text": "STOP"}, ("command", "STOP", [])),
        ("audio", {"media_id": "123", "mime_type": "audio/ogg"}, ("voice", None, [])),
        ("image", {"media_id": "123", "mime_type": "image/jpeg"}, ("photo", None, [])),
        ("document", {"media_id": "123", "mime_type": "application/pdf"}, ("document", None, [])),
        ("button", {"button_id": f"fb1:{PROMPT}:undo"}, ("tap", None, ["undo"])),
    ],
)
def test_inbound_rows_keep_the_kind_words_and_tapped_choice(
    kind: str, changes: dict[str, object], expected: tuple[str, str | None, list[str]]
) -> None:
    session = session_for(standing())
    receipt_id = uuid4()
    store.add_inbound(
        session, True, user_id=uuid4(), receipt_id=receipt_id, question=question(kind, **changes)
    )
    row = added(session)
    assert (row.kind, row.text, row.choices) == expected
    assert row.direction == "in" and row.receipt_id == receipt_id and row.created_at == NOW


def test_sent_rows_are_cleaned_and_keep_only_known_languages() -> None:
    session = session_for(standing())
    store.add_sent(
        session,
        True,
        user_id=uuid4(),
        kind="buttons",
        text="Saved ₹500 from 98765432109@ybl",
        choices=["↩️ Undo"],
        outcome="sent",
        language="fr",
    )
    row = added(session)
    assert row.direction == "out" and row.kind == "buttons" and row.outcome == "sent"
    assert row.text == "Saved ₹500 from [UPI ID]" and row.choices == ["↩️ Undo"]
    assert row.language is None


def test_a_failed_log_write_never_reaches_the_caller(caplog: pytest.LogCaptureFixture) -> None:
    session = session_for(standing())
    session.begin_nested.side_effect = OperationalError("synthetic", {}, Exception("x"))
    store.add_sent(session, True, user_id=uuid4(), kind="text", text="Hi", outcome="sent")
    assert "conversation.log_failed" in caplog.text


def test_downloads_skip_statement_pdfs_and_go_to_r2_once(
    kept: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    put = MagicMock()
    monkeypatch.setattr(r2, "put", put)
    row = ConversationMessage(id=uuid4(), user_id=uuid4(), direction="in", kind="voice")
    session = MagicMock(spec=Session)
    session.scalar.return_value = row
    store.keep_downloads(
        session, kept, uuid4(), [DownloadedMedia(b"%PDF-synthetic", "application/pdf")]
    )
    put.assert_not_called()
    store.keep_downloads(session, kept, uuid4(), [DownloadedMedia(b"OggS-synthetic", "audio/ogg")])
    key = f"finboy-conversations-dev/{row.user_id}/{row.id}.ogg"
    put.assert_called_once_with(kept, key, b"OggS-synthetic", "audio/ogg")
    assert (row.media_key, row.media_type, row.media_bytes) == (key, "audio/ogg", 14)
    session.commit.assert_called_once()


def test_downloads_are_dropped_when_off_or_unreachable(
    settings: Settings, kept: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = MagicMock(spec=Session)
    media = [DownloadedMedia(b"synthetic", "image/jpeg")]
    store.keep_downloads(session, settings, uuid4(), media)  # flag off: not even a query
    session.scalar.assert_not_called()

    session.scalar.return_value = ConversationMessage(id=uuid4(), user_id=uuid4(), kind="photo")
    monkeypatch.setattr(r2, "put", MagicMock(side_effect=r2.StoreUnavailable))
    store.keep_downloads(session, kept, uuid4(), media)
    session.commit.assert_not_called()
    session.rollback.assert_called_once()


def test_keeping_media_never_breaks_processing(settings: Settings, kept: Settings) -> None:
    factory = MagicMock(side_effect=OperationalError("synthetic", {}, Exception("x")))
    client = SimpleNamespace(downloads=[DownloadedMedia(b"OggS", "audio/ogg")])
    processor.keep_media(factory, settings, uuid4(), client)  # off: nothing is touched
    factory.assert_not_called()
    processor.keep_media(factory, kept, uuid4(), client)  # on, database down: swallowed
    assert client.downloads == []
    processor.keep_media(factory, kept, uuid4(), SimpleNamespace())  # a client without any


def test_removal_deletes_the_r2_folder_before_any_row(
    kept: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    order: list[str] = []
    monkeypatch.setattr(r2, "delete_folder", lambda *_: order.append("files") or 2)
    session = MagicMock(spec=Session)
    session.scalar.return_value = True
    session.execute.side_effect = lambda *_: order.append("rows") or SimpleNamespace(rowcount=3)
    assert store.remove(session, kept, uuid4()) == 3
    assert order == ["files", "rows"]


def test_removal_waits_rather_than_leave_files_behind(
    settings: Settings, kept: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(r2, "delete_folder", MagicMock(side_effect=r2.StoreUnavailable))
    session = MagicMock(spec=Session)
    session.scalar.return_value = True
    with pytest.raises(AccessError) as unreachable:
        store.remove(session, kept, uuid4())
    assert unreachable.value.code == "try_later"
    with pytest.raises(AccessError):
        store.remove(session, None, uuid4())  # files exist and R2 isn't configured
    session.execute.assert_not_called()


def test_removal_without_rows_never_calls_r2(
    kept: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    folder = MagicMock()
    monkeypatch.setattr(r2, "delete_folder", folder)
    session = MagicMock(spec=Session)
    session.scalar.return_value = False
    assert store.remove(session, kept, uuid4()) == 0
    folder.assert_not_called()
