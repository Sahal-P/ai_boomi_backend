"""Stateless loopback proxy: tunnel this port, never the FinBoy product API."""

import argparse
import asyncio

import httpx
import uvicorn
from starlette.types import Receive, Scope, Send

WEBHOOK_PATH = "/api/v1/whatsapp/webhook"
MAX_BODY = 262144
FORWARDED_HEADERS = {b"content-type", b"content-length", b"x-hub-signature-256"}


class WebhookIngress:
    def __init__(self, api_port: int) -> None:
        if not 1024 <= api_port <= 65535:
            raise ValueError("Invalid loopback API port")
        self.upstream = f"http://127.0.0.1:{api_port}{WEBHOOK_PATH}"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            return
        status, content = 404, b"Not Found"
        if (
            scope.get("path") != WEBHOOK_PATH
            or scope.get("raw_path", WEBHOOK_PATH.encode()) != WEBHOOK_PATH.encode()
            or scope.get("method") not in {"GET", "POST"}
        ):
            await self.respond(send, status, content)
            return
        # Unknown/encoded/normalized paths never reach the API. No host/header routing.
        if len(scope.get("query_string", b"")) > 2048:
            await self.respond(send, 400, b"Bad Request")
            return
        raw = bytearray()
        try:
            async with asyncio.timeout(15):
                while True:
                    event = await receive()
                    if event["type"] == "http.disconnect":
                        return
                    raw.extend(event.get("body", b""))
                    if len(raw) > MAX_BODY:
                        await self.respond(send, 413, b"Payload Too Large")
                        return
                    if not event.get("more_body", False):
                        break
            headers = [
                (key, value) for key, value in scope["headers"] if key.lower() in FORWARDED_HEADERS
            ]
            if any(key.lower() == b"content-encoding" for key, _ in scope["headers"]):
                await self.respond(send, 415, b"Unsupported Media Type")
                return
            query = scope.get("query_string", b"")
            url = self.upstream + ("?" + query.decode("ascii") if query else "")
            async with (
                httpx.AsyncClient(timeout=15, trust_env=False, follow_redirects=False) as client,
                asyncio.timeout(20),
                client.stream(
                    scope["method"], url, content=bytes(raw), headers=headers
                ) as response,
            ):
                if 300 <= response.status_code < 400:
                    await self.respond(send, 502, b"Bad Gateway")
                    return
                data = bytearray()
                async for chunk in response.aiter_bytes():
                    data.extend(chunk)
                    if len(data) > 32768:
                        raise ValueError
                status, content = response.status_code, bytes(data)
        except httpx.HTTPError, TimeoutError, ValueError, UnicodeError:
            status, content = 503, b"Service Unavailable"
        await self.respond(send, status, content)

    @staticmethod
    async def respond(send: Send, status: int, content: bytes) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [
                    (b"content-type", b"text/plain; charset=utf-8"),
                    (b"cache-control", b"no-store"),
                    (b"content-length", str(len(content)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": content})


def main() -> None:
    parser = argparse.ArgumentParser(description="Webhook-only loopback ingress; no product routes")
    parser.add_argument("--api-port", type=int, default=8014)
    parser.add_argument("--port", type=int, default=8094)
    args = parser.parse_args()
    uvicorn.run(
        WebhookIngress(args.api_port),
        host="127.0.0.1",
        port=args.port,
        access_log=False,
        lifespan="off",
        server_header=False,
    )


if __name__ == "__main__":
    main()
