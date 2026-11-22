"""The message log end to end on PostgreSQL (docs/conversation-round/contract.md): what a household
that agreed sends and is sent, its voice notes in a fake R2, the admin view, export, clearing and
erasure. Synthetic numbers and words only."""

from collections.abc import Iterator
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from finboy.core.config import LOCAL_USER_ID, Settings
from finboy.core.errors import AccessError
from finboy.db.models.advisor import AdvisorMessage, AdvisorThread
from finboy.db.models.conversations import ConversationMessage
from finboy.db.models.core import User
from finboy.db.models.whatsapp import WhatsAppBinding
from finboy.db.session import build_engine
from finboy.services.accounts import households
from finboy.services.admin import messages
from finboy.services.conversations import r2, store
from finboy.services.whatsapp.config import ChannelConfig
from finboy.services.whatsapp.events import InboundQuestion, Status
from finboy.services.whatsapp.meta import DownloadedMedia
from finboy.services.whatsapp.processor import send_reply
from finboy.services.whatsapp.receipts import admit, claim
from sqlalchemy import delete, func, select, update
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

pytestmark = pytest.mark.integration
SENDER = "919000000001"  # the owner's synthetic number in the test allowlist
DISPOSABLE = {"finboy_signup", "finboy_admin", "finboy_advisor", "finboy_test"}


class Client:
    """Meta stand-in: every send is accepted with a fresh synthetic ID."""

    def _id(self, *_args: object, **_kwargs: object) -> str:
        return "wamid.out." + uuid4().hex

    send = send_buttons = send_list = _id


@pytest.fixture
def factory(config: ChannelConfig) -> Iterator[sessionmaker[Session]]:
    settings = Settings()
    url = make_url(settings.database_url.get_secret_value())
    if (
        settings.environment == "production"
        or url.host not in {"127.0.0.1", "localhost"}
        or url.database not in DISPOSABLE
    ):
        pytest.fail("Conversation tests require a disposable local FinBoy integration database")
    engine = build_engine(settings)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as session:
        owner_from = session.scalar(select(User.messages_kept_from).where(User.id == LOCAL_USER_ID))
    try:
        yield factory
    finally:
        with factory() as session:
            session.execute(
                delete(ConversationMessage).where(ConversationMessage.user_id == LOCAL_USER_ID)
            )
            session.execute(delete(AdvisorThread).where(AdvisorThread.user_id == LOCAL_USER_ID))
            session.execute(
                delete(WhatsAppBinding).where(
                    WhatsAppBinding.sender_hash == config.digest("sender", SENDER)
                )
            )
            session.execute(
                update(User)
                .where(User.id == LOCAL_USER_ID)
                .values(messages_kept_from=owner_from, messages_declined_at=None)
            )
            session.commit()
        engine.dispose()


@pytest.fixture
def kept(config: ChannelConfig) -> ChannelConfig:
    return replace(config, messages=True)


@pytest.fixture
def media_settings(wa_settings: Settings) -> Settings:
    return Settings(
        **{
            **wa_settings.model_dump(),
            "conversation_log_enabled": True,
            "r2_account_id": "0" * 32,
            "r2_access_key_id": "synthetic-access",
            "r2_secret_access_key": "synthetic-secret",
            "r2_bucket": "synthetic-bucket",
        },
        _env_file=None,
    )


@pytest.fixture
def bucket(monkeypatch: pytest.MonkeyPatch) -> dict[str, bytes]:
    files: dict[str, bytes] = {}

    def put(_settings: Settings, key: str, data: bytes, _content_type: str) -> None:
        files[key] = data

    def get(_settings: Settings, key: str) -> bytes:
        if key not in files:
            raise r2.StoreUnavailable
        return files[key]

    def delete_folder(settings: Settings, user_id: UUID) -> int:
        doomed = [key for key in files if key.startswith(r2.folder(settings, user_id))]
        for key in doomed:
            del files[key]
        return len(doomed)

    monkeypatch.setattr(r2, "put", put)
    monkeypatch.setattr(r2, "get", get)
    monkeypatch.setattr(r2, "delete_folder", delete_folder)
    return files


def inbound(kind: str = "text", text: str = "", **changes: object) -> InboundQuestion:
    return InboundQuestion(
        "wamid." + uuid4().hex,
        SENDER,
        datetime.now(UTC),
        kind,  # type: ignore[arg-type]
        text,
        **changes,  # type: ignore[arg-type]
    )


def rows(session: Session) -> list[ConversationMessage]:
    return list(
        session.scalars(
            select(ConversationMessage)
            .where(ConversationMessage.user_id == LOCAL_USER_ID)
            .order_by(ConversationMessage.created_at, ConversationMessage.id)
        )
    )


def test_a_household_that_agreed_has_its_whole_conversation_kept(
    factory: sessionmaker[Session],
    kept: ChannelConfig,
    media_settings: Settings,
    bucket: dict[str, bytes],
) -> None:
    client = Client()
    with factory() as session:
        typed = inbound(text="paid 500 to ramesh@okicici")
        voice = inbound("audio", media_id="123456", mime_type="audio/ogg")
        tap = inbound("button", button_id="fb1:" + "a" * 32 + ":undo")
        admitted = {item.question.message_id: item for item in admit(session, kept, [typed], [])}
        admitted |= {item.question.message_id: item for item in admit(session, kept, [voice], [])}
        admitted |= {item.question.message_id: item for item in admit(session, kept, [tap], [])}
        assert [(row.kind, row.text, row.choices) for row in rows(session)] == [
            ("text", "paid 500 to [UPI ID]", []),
            ("voice", None, []),
            ("tap", None, ["undo"]),
        ]

        receipt = claim(session, admitted[typed.message_id].receipt_id)
        assert send_reply(
            session,
            kept,
            client,
            receipt,
            typed,
            text="✅ Saved ₹500 · Ramesh",
            buttons=[("fb1:" + "b" * 32 + ":undo", "↩️ Undo")],
        )
        reply = rows(session)[-1]
        assert (reply.direction, reply.kind, reply.choices, reply.outcome) == (
            "out",
            "buttons",
            ["↩️ Undo"],
            "sent",
        )

        heard = claim(session, admitted[voice.message_id].receipt_id)
        store.note_transcript(session.get_bind(), heard.id, "doodhwale ko 500 diye", "hi")
        assert send_reply(session, kept, client, heard, voice, media_id="999", spoken="Added.")
    with factory() as session:
        store.keep_downloads(
            session,
            media_settings,
            heard.id,
            [DownloadedMedia(b"OggS synthetic voice", "audio/ogg")],
        )
    with factory() as session:
        delivered = session.scalar(
            select(ConversationMessage.delivery_id).where(ConversationMessage.id == reply.id)
        )
        assert delivered is not None
        page = messages.page(session, LOCAL_USER_ID, None)
        voice_row = next(item for item in page.items if item.kind == "voice")
        assert voice_row.transcript == "doodhwale ko 500 diye" and voice_row.language == "hi"
        assert voice_row.media == "audio" and voice_row.media_bytes == 20
        spoken = next(item for item in page.items if item.kind == "voice_reply")
        assert spoken.text == "Added." and spoken.direction == "out"
        found = messages.media(session, media_settings, voice_row.id)
        assert found.data == b"OggS synthetic voice" and found.content_type == "audio/ogg"
        assert [item.at for item in page.items] == sorted(
            (item.at for item in page.items), reverse=True
        )

        exported = store.exported(session, LOCAL_USER_ID)
        assert any(item["transcript"] == "doodhwale ko 500 diye" for item in exported)
        assert all("media_key" not in item for item in exported)

        assert store.remove(session, media_settings, LOCAL_USER_ID) == 5
        session.commit()
        assert rows(session) == [] and bucket == {}


def test_delivery_and_read_states_reach_the_admin_view(
    factory: sessionmaker[Session], kept: ChannelConfig
) -> None:
    with factory() as session:
        asked = inbound(text="chai 20")
        item = admit(session, kept, [asked], [])[0]
        receipt = claim(session, item.receipt_id)

        class Fixed(Client):
            def send(self, *_args: object, **_kwargs: object) -> str:
                return "wamid.outbound.read"

        assert send_reply(session, kept, Fixed(), receipt, asked, text="✅ Saved ₹20")
        admit(
            session,
            kept,
            [],
            [Status(id="wamid.outbound.read", status="read", recipient_id=SENDER)],
        )
        page = messages.page(session, LOCAL_USER_ID, None)
        assert page.items[0].direction == "out" and page.items[0].status == "read"


def test_messages_sent_in_the_same_second_page_without_gaps(
    factory: sessionmaker[Session],
) -> None:
    with factory() as session:
        second = datetime.now(UTC).replace(microsecond=0)
        for index in range(messages.PAGE + 2):
            session.add(
                ConversationMessage(
                    user_id=LOCAL_USER_ID,
                    direction="in",
                    kind="text",
                    text=f"forwarded {index}",
                    created_at=second,
                )
            )
        session.commit()
        first = messages.page(session, LOCAL_USER_ID, None)
        assert len(first.items) == messages.PAGE and first.next_before is not None
        rest = messages.page(session, LOCAL_USER_ID, first.next_before)
        assert rest.next_before is None
        shown = [item.id for item in first.items + rest.items]
        assert len(shown) == len(set(shown)) == messages.PAGE + 2


def test_web_ask_chats_join_only_from_the_day_the_household_agreed(
    factory: sessionmaker[Session],
) -> None:
    with factory() as session:
        agreed = datetime.now(UTC) - timedelta(days=1)
        session.execute(
            update(User).where(User.id == LOCAL_USER_ID).values(messages_kept_from=agreed)
        )
        thread = AdvisorThread(user_id=LOCAL_USER_ID, channel="web")
        session.add(thread)
        session.flush()
        for text, at in (
            ("before agreeing", agreed - timedelta(days=3)),
            ("can i afford a bike", agreed + timedelta(hours=1)),
        ):
            session.add(
                AdvisorMessage(
                    thread_id=thread.id,
                    user_id=LOCAL_USER_ID,
                    role="user",
                    text=text,
                    created_at=at,
                )
            )
        session.commit()
        page = messages.page(session, LOCAL_USER_ID, None)
        web = [item.text for item in page.items if item.channel == "web"]
        assert web == ["can i afford a bike"]


def test_nothing_is_kept_without_agreement_while_off_or_after_stop(
    factory: sessionmaker[Session], config: ChannelConfig, kept: ChannelConfig
) -> None:
    with factory() as session:
        admit(session, config, [inbound(text="flag is off")], [])
        session.execute(
            update(User).where(User.id == LOCAL_USER_ID).values(messages_kept_from=None)
        )
        session.commit()
        admit(session, kept, [inbound(text="never agreed")], [])
        assert rows(session) == []
        session.execute(
            update(User)
            .where(User.id == LOCAL_USER_ID)
            .values(messages_kept_from=datetime.now(UTC))
        )
        session.commit()
        admit(session, kept, [inbound(text="STOP")], [])
        admit(session, kept, [inbound(text="after stop")], [])
        assert [(row.kind, row.text) for row in rows(session)] == [("command", "STOP")]


def test_erasure_removes_kept_messages_and_every_file_first(
    factory: sessionmaker[Session], media_settings: Settings, bucket: dict[str, bytes]
) -> None:
    with factory() as session:
        user = households.new_household(session, joined_via="whatsapp", agreed=True)
        user.messages_kept_from = datetime.now(UTC)
        session.flush()
        row = ConversationMessage(user_id=user.id, direction="in", kind="voice")
        session.add(row)
        session.flush()
        key = r2.key_for(media_settings, user.id, row.id, "audio/ogg")
        row.media_key, row.media_type, row.media_bytes = key, "audio/ogg", 9
        bucket[key] = b"synthetic"
        bucket[r2.folder(media_settings, user.id) + "orphan.jpg"] = b"left by a failed write"
        session.commit()
        try:
            with pytest.raises(AccessError):
                households.remove_household_data(session, user.id)  # no settings, files exist
            session.rollback()
            counts = households.erase_household(session, user.id, media_settings)
            session.commit()
            assert counts["conversation_messages"] == 1 and bucket == {}
            remaining = session.scalar(
                select(func.count())
                .select_from(ConversationMessage)
                .where(ConversationMessage.user_id == user.id)
            )
            assert remaining == 0
        finally:
            session.rollback()
            session.execute(
                delete(ConversationMessage).where(ConversationMessage.user_id == user.id)
            )
            session.execute(delete(User).where(User.id == user.id))
            session.commit()
