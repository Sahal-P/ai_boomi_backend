"""Only signed, allowlisted WhatsApp ledger questions. No arbitrary send endpoint."""

import asyncio
import hmac

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import sessionmaker
from starlette.concurrency import run_in_threadpool

from finboy.services.whatsapp.config import ChannelUnavailable, channel_config
from finboy.services.whatsapp.events import InvalidWebhook, parse_events, verify_signature
from finboy.services.whatsapp.processor import process_question
from finboy.services.whatsapp.receipts import Admission, admit

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])


@router.get("/webhook", response_class=PlainTextResponse, include_in_schema=False)
def verify_webhook(request: Request) -> PlainTextResponse:
    try:
        config = channel_config(request.app.state.settings)
    except ChannelUnavailable:
        raise HTTPException(503) from None
    params = request.query_params
    if any(
        len(params.getlist(key)) != 1 for key in ("hub.mode", "hub.verify_token", "hub.challenge")
    ):
        raise HTTPException(403)
    token = params.get("hub.verify_token", "")
    challenge = params.get("hub.challenge", "")
    if (
        params.get("hub.mode") != "subscribe"
        or len(token) > 512
        or not hmac.compare_digest(token.encode(), config.verify_token.encode())
        or not challenge.isascii()
        or not challenge.isdigit()
        or not 1 <= len(challenge) <= 128
    ):
        raise HTTPException(403)
    return PlainTextResponse(challenge, headers={"Cache-Control": "no-store"})


@router.post("/webhook", include_in_schema=False)
async def receive_webhook(request: Request, tasks: BackgroundTasks) -> dict[str, str]:
    try:
        config = channel_config(request.app.state.settings)
    except ChannelUnavailable:
        raise HTTPException(503) from None
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
        raise HTTPException(415)
    if request.headers.get("content-encoding", "identity").lower() != "identity":
        raise HTTPException(415)
    length = request.headers.get("content-length")
    if length and (not length.isdigit() or int(length) > config.max_body):
        raise HTTPException(413)
    raw = bytearray()
    try:
        async with asyncio.timeout(config.timeout):
            async for chunk in request.stream():
                if len(raw) + len(chunk) > config.max_body:
                    raise HTTPException(413)
                raw.extend(chunk)
    except TimeoutError:
        raise HTTPException(408) from None
    if len(request.headers.getlist("x-hub-signature-256")) != 1 or not verify_signature(
        bytes(raw), request.headers.get("x-hub-signature-256", ""), config
    ):
        raise HTTPException(403)
    try:
        questions, statuses = parse_events(bytes(raw), config)
    except InvalidWebhook:
        raise HTTPException(400) from None
    factory = sessionmaker(bind=request.app.state.engine, expire_on_commit=False)

    def persist() -> list[Admission]:
        with factory() as session:
            return admit(session, config, questions, statuses)

    try:
        admitted = await run_in_threadpool(persist)
    except Exception:
        raise HTTPException(503) from None
    for item in admitted:
        tasks.add_task(
            process_question,
            factory,
            request.app.state.settings,
            config,
            item.receipt_id,
            item.question,
        )
    return {"status": "accepted"}
