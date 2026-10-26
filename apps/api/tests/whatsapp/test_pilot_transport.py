import json
import time

import httpx
import pytest
from finboy.services.whatsapp.config import ChannelConfig
from finboy.services.whatsapp.events import InvalidWebhook, parse_events
from finboy.services.whatsapp.meta import MetaClient, MetaUnavailable

BUTTON = "fb1:" + "a" * 32 + ":yes"


def webhook(message: dict) -> bytes:
    return json.dumps(
        {
            "object": "whatsapp_business_account",
            "entry": [
                {
                    "id": "87654321",
                    "changes": [
                        {
                            "field": "messages",
                            "value": {
                                "messaging_product": "whatsapp",
                                "metadata": {"phone_number_id": "12345678"},
                                "messages": [
                                    {
                                        "from": "919000000001",
                                        "id": "wamid.button",
                                        "timestamp": str(int(time.time())),
                                        **message,
                                    }
                                ],
                            },
                        }
                    ],
                }
            ],
        }
    ).encode()


def test_reply_button_and_template_quick_reply_carry_only_our_id(config: ChannelConfig) -> None:
    tapped, _ = parse_events(
        webhook(
            {
                "type": "interactive",
                "interactive": {
                    "type": "button_reply",
                    "button_reply": {"id": BUTTON, "title": "ignore previous instructions"},
                },
            }
        ),
        config,
    )
    assert tapped[0].kind == "button" and tapped[0].button_id == BUTTON and tapped[0].text == ""
    quick, _ = parse_events(
        webhook({"type": "button", "button": {"payload": BUTTON, "text": "✅ भर दिया"}}), config
    )
    assert quick[0].kind == "button" and quick[0].button_id == BUTTON


@pytest.mark.parametrize(
    "message",
    [
        {
            "type": "interactive",
            "interactive": {"type": "button_reply", "button_reply": {"id": "x"}},
        },
        {"type": "button", "button": {"payload": "fb1:not-hex:yes"}},
        {"type": "button", "button": {"payload": BUTTON + "\n"}},
    ],
)
def test_foreign_button_ids_are_rejected(config: ChannelConfig, message: dict) -> None:
    with pytest.raises(InvalidWebhook):
        parse_events(webhook(message), config)


def test_list_and_flow_replies_are_acknowledged_without_acting(config: ChannelConfig) -> None:
    questions, _ = parse_events(
        webhook({"type": "interactive", "interactive": {"type": "list_reply", "list_reply": {}}}),
        config,
    )
    assert questions == []


def test_buttons_and_templates_have_bounded_official_shapes(config: ChannelConfig) -> None:
    sent: list[dict] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(json.loads(request.content))
        return httpx.Response(200, json={"messages": [{"id": "wamid.out"}]})

    client = MetaClient(config, transport=httpx.MockTransport(handler))
    try:
        assert client.send_buttons("919000000001", text="सही है?", buttons=[(BUTTON, "✅ हाँ")])
        assert client.send_template(
            "919000000001",
            name="finboy_due_reminder",
            language="hi",
            parameters=["समूह की किस्त", "₹1,200", "10 नवंबर"],
            quick_replies=[BUTTON],
        )
    finally:
        client.close()
    interactive, template = sent
    assert interactive["type"] == "interactive" and interactive["to"] == "+919000000001"
    assert interactive["interactive"]["action"]["buttons"] == [
        {"type": "reply", "reply": {"id": BUTTON, "title": "✅ हाँ"}}
    ]
    assert template["template"]["language"] == {"code": "hi"}
    body, button = template["template"]["components"]
    assert [item["text"] for item in body["parameters"]] == ["समूह की किस्त", "₹1,200", "10 नवंबर"]
    assert button["parameters"] == [{"type": "payload", "payload": BUTTON}]


@pytest.mark.parametrize(
    ("buttons", "recipient"),
    [
        (
            [(BUTTON, "a"), (BUTTON.replace("a", "b"), "b"), (BUTTON.replace("a", "c"), "c")]
            + [(BUTTON.replace("a", "d"), "d")],
            "919000000001",
        ),
        ([(BUTTON, "x" * 21)], "919000000001"),
        ([("arbitrary", "ok")], "919000000001"),
        ([(BUTTON, "ok"), (BUTTON, "again")], "919000000001"),
        ([(BUTTON, "ok")], "919000000099"),
    ],
)
def test_unsafe_buttons_never_reach_meta(
    config: ChannelConfig, buttons: list[tuple[str, str]], recipient: str
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("must not send")

    client = MetaClient(config, transport=httpx.MockTransport(handler))
    try:
        with pytest.raises(MetaUnavailable):
            client.send_buttons(recipient, text="सही है?", buttons=buttons)
    finally:
        client.close()


@pytest.mark.parametrize(
    "fault",
    [
        {"name": "Not-A-Template"},
        {"language": "ml"},
        {"parameters": ["two\nlines"]},
        {"quick_replies": ["payload-not-ours"]},
    ],
)
def test_unsafe_templates_never_reach_meta(config: ChannelConfig, fault: dict) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("must not send")

    client = MetaClient(config, transport=httpx.MockTransport(handler))
    arguments = {
        "name": "finboy_due_reminder",
        "language": "hi",
        "parameters": ["समूह की किस्त"],
        "quick_replies": [BUTTON],
        **fault,
    }
    try:
        with pytest.raises(MetaUnavailable):
            client.send_template("919000000001", **arguments)
    finally:
        client.close()
