import httpx
import pytest
from finboy.services.whatsapp.ingress import WebhookIngress


@pytest.mark.anyio
@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/docs",
        "/openapi.json",
        "/api/v1/health",
        "/api/v1/money/summary",
        "/api/v1/transactions",
        "/api/v1/privacy/imported-data",
        "/api/v1/assistant/ask",
        "/api/v1/whatsapp/send",
        "/api/v1/whatsapp/webhook/",
        "/api/v1/whatsapp/%77ebhook",
        "/api/v1/whatsapp/webhook%2F..%2F..%2Fmoney",
    ],
)
async def test_proxy_denies_every_other_route(path: str) -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=WebhookIngress(1 + 8013)), base_url="http://ingress"
    ) as client:
        for method in ["GET", "POST", "PATCH", "DELETE", "OPTIONS"]:
            response = await client.request(method, path)
            assert response.status_code == 404


@pytest.mark.anyio
async def test_proxy_denies_other_webhook_methods() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=WebhookIngress(8014)), base_url="http://ingress"
    ) as client:
        for method in ["PATCH", "DELETE", "OPTIONS", "PUT", "HEAD"]:
            assert (await client.request(method, "/api/v1/whatsapp/webhook")).status_code == 404
