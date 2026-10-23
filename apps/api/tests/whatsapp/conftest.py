import json

import pytest
from finboy.core.config import LOCAL_USER_ID, Settings
from finboy.services.whatsapp.config import ChannelConfig, channel_config


@pytest.fixture
def wa_settings(settings: Settings) -> Settings:
    return Settings(
        **{
            **settings.model_dump(),
            "whatsapp_enabled": True,
            "whatsapp_app_id": "953180210789448",
            "whatsapp_graph_api_version": "v26.0",
            "whatsapp_app_secret": "synthetic-app-secret",
            "whatsapp_verify_token": "synthetic-verify",
            "whatsapp_access_token": "synthetic-access",
            "whatsapp_phone_number_id": "12345678",
            "whatsapp_business_account_id": "87654321",
            "token_encryption_key": "eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHh4eHg=",
            "whatsapp_sender_allowlist_json": json.dumps({"919000000001": str(LOCAL_USER_ID)}),
        },
        _env_file=None,
    )


@pytest.fixture
def config(wa_settings: Settings) -> ChannelConfig:
    return channel_config(wa_settings)


def payload(
    *,
    sender: str = "919000000001",
    text: str = "food this month?",
    message_id: str = "wamid.synthetic",
    kind: str = "text",
) -> dict:
    import time

    return {
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
                                    "from": sender,
                                    "id": message_id,
                                    "timestamp": str(int(time.time())),
                                    "type": kind,
                                    **(
                                        {"text": {"body": text}}
                                        if kind == "text"
                                        else {
                                            "audio": {
                                                "id": "1234",
                                                "mime_type": "audio/ogg; codecs=opus",
                                            }
                                        }
                                    ),
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }
