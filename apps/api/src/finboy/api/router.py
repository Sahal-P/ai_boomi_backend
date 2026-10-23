from fastapi import APIRouter

from finboy.api.v1.assistant import router as assistant_router
from finboy.api.v1.connections import router as connections_router
from finboy.api.v1.health import router as health_router
from finboy.api.v1.imports import router as imports_router
from finboy.api.v1.money import router as money_router
from finboy.api.v1.privacy import router as privacy_router
from finboy.api.v1.transactions import router as transactions_router
from finboy.api.v1.whatsapp import router as whatsapp_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health_router)
api_router.include_router(connections_router)
api_router.include_router(imports_router)
api_router.include_router(privacy_router)
api_router.include_router(assistant_router)
api_router.include_router(money_router)
api_router.include_router(transactions_router)

api_router.include_router(whatsapp_router)
