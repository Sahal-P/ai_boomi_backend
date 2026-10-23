"""Agent 4 adds only the verified webhook GET/POST routes after bootstrap."""

from fastapi import APIRouter

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])
