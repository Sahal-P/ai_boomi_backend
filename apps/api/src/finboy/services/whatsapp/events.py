"""Bounded Meta event validation; bodies and questions live only in request memory."""

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from finboy.services.whatsapp.config import ChannelConfig


class InvalidWebhook(Exception):
    pass


# Hindi बंद/शुरू work like STOP/START for households who don't type English.
COMMANDS = {
    "stop": "stop",
    "start": "start",
    "en": "en",
    "hi": "hi",
    "ml": "ml",
    "बंद": "stop",
    "शुरू": "start",
}


@dataclass(frozen=True)
class InboundQuestion:
    message_id: str
    sender: str = field(repr=False)
    provider_at: datetime
    kind: Literal["text", "audio", "image", "button"]
    text: str = field(default="", repr=False)
    media_id: str | None = None
    mime_type: str | None = None
    # Our own opaque reply-button ID (fb1:<prompt>:<choice>); never the button's title.
    button_id: str | None = None

    @property
    def command(self) -> str | None:
        return COMMANDS.get(self.text.strip().lower())


class TextBody(BaseModel):
    body: str = Field(min_length=1, max_length=2000, repr=False)


class AudioBody(BaseModel):
    id: str = Field(pattern=r"^[0-9]{1,64}$")
    mime_type: str = Field(min_length=1, max_length=100)


class ImageBody(AudioBody):
    """Only the Graph media ID and MIME are read; caption and webhook URL are ignored."""


BUTTON_ID = r"^fb1:[0-9a-f]{32}:[a-z]{2,8}$"


class ButtonReply(BaseModel):
    """Only our opaque ID is read; the displayed title is ignored."""

    id: str = Field(pattern=BUTTON_ID)


class InteractiveBody(BaseModel):
    type: str = Field(max_length=32)
    button_reply: ButtonReply | None = None


class TemplateButton(BaseModel):
    """A template quick reply carries our ID as its payload."""

    payload: str = Field(pattern=BUTTON_ID)


class Message(BaseModel):
    id: str = Field(min_length=1, max_length=256, pattern=r"^[A-Za-z0-9_.=+/-]+$")
    from_: str = Field(alias="from", pattern=r"^[0-9]{7,20}$", repr=False)
    timestamp: str = Field(pattern=r"^[0-9]{1,12}$")
    type: str = Field(max_length=64)
    text: TextBody | None = None
    audio: AudioBody | None = None
    image: ImageBody | None = None
    interactive: InteractiveBody | None = None
    button: TemplateButton | None = None


class Status(BaseModel):
    id: str = Field(min_length=1, max_length=256)
    status: Literal["sent", "delivered", "read", "failed"]
    recipient_id: str = Field(pattern=r"^[0-9]{7,20}$", repr=False)


def verify_signature(raw: bytes, signature: str, config: ChannelConfig) -> bool:
    expected = "sha256=" + hmac.new(config.app_secret.encode(), raw, hashlib.sha256).hexdigest()
    return len(signature) == 71 and hmac.compare_digest(signature.encode(), expected.encode())


def parse_events(raw: bytes, config: ChannelConfig) -> tuple[list[InboundQuestion], list[Status]]:
    try:
        data = json.loads(raw)
        if not isinstance(data, dict) or data.get("object") != "whatsapp_business_account":
            raise InvalidWebhook
        entries = data.get("entry", [])
        if not isinstance(entries, list) or len(entries) > 16:
            raise InvalidWebhook
        questions: list[InboundQuestion] = []
        statuses: list[Status] = []
        for entry in entries:
            if not isinstance(entry, dict) or entry.get("id") != config.account_id:
                raise InvalidWebhook
            changes = entry.get("changes", [])
            if not isinstance(changes, list) or len(changes) > 16:
                raise InvalidWebhook
            for change in changes:
                if not isinstance(change, dict):
                    raise InvalidWebhook
                if change.get("field") != "messages":
                    continue
                value = change.get("value")
                if not isinstance(value, dict) or value.get("messaging_product") != "whatsapp":
                    raise InvalidWebhook
                metadata = value.get("metadata")
                if (
                    not isinstance(metadata, dict)
                    or metadata.get("phone_number_id") != config.phone_id
                ):
                    raise InvalidWebhook
                messages, updates = value.get("messages", []), value.get("statuses", [])
                if not isinstance(messages, list) or not isinstance(updates, list):
                    raise InvalidWebhook
                if len(messages) > 32 or len(updates) > 64:
                    raise InvalidWebhook
                for item in messages:
                    if not isinstance(item, dict):
                        raise InvalidWebhook
                    if item.get("type") not in {"text", "audio", "image", "interactive", "button"}:
                        continue
                    interactive = item.get("interactive")
                    if item.get("type") == "interactive" and (
                        not isinstance(interactive, dict)
                        or interactive.get("type") != "button_reply"
                    ):
                        # List/flow replies are not used by FinBoy; acknowledge without acting.
                        continue
                    msg = Message.model_validate(item)
                    when = datetime.fromtimestamp(int(msg.timestamp), UTC)
                    if msg.type == "text" and msg.text is not None:
                        questions.append(
                            InboundQuestion(msg.id, msg.from_, when, "text", msg.text.body)
                        )
                    elif msg.type == "audio" and msg.audio is not None:
                        questions.append(
                            InboundQuestion(
                                msg.id,
                                msg.from_,
                                when,
                                "audio",
                                media_id=msg.audio.id,
                                mime_type=msg.audio.mime_type,
                            )
                        )
                    elif msg.type == "image" and msg.image is not None:
                        questions.append(
                            InboundQuestion(
                                msg.id,
                                msg.from_,
                                when,
                                "image",
                                media_id=msg.image.id,
                                mime_type=msg.image.mime_type,
                            )
                        )
                    elif (
                        msg.type == "interactive"
                        and msg.interactive is not None
                        and msg.interactive.button_reply is not None
                    ):
                        questions.append(
                            InboundQuestion(
                                msg.id,
                                msg.from_,
                                when,
                                "button",
                                button_id=msg.interactive.button_reply.id,
                            )
                        )
                    elif msg.type == "button" and msg.button is not None:
                        questions.append(
                            InboundQuestion(
                                msg.id, msg.from_, when, "button", button_id=msg.button.payload
                            )
                        )
                    else:
                        raise InvalidWebhook
                for update in updates:
                    # Future provider statuses are acknowledged safely, with no invented transition.
                    if isinstance(update, dict) and update.get("status") in {
                        "sent",
                        "delivered",
                        "read",
                        "failed",
                    }:
                        statuses.append(Status.model_validate(update))
        if len(questions) > 32 or len(statuses) > 64:
            raise InvalidWebhook
        return questions, statuses
    except ValueError, TypeError, OverflowError, OSError, ValidationError, RecursionError:
        raise InvalidWebhook from None
