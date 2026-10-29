from fastapi import APIRouter

from finboy.api.v1.account import router as account_router
from finboy.api.v1.assistant import router as assistant_router
from finboy.api.v1.auth import router as auth_router
from finboy.api.v1.budgets import router as budgets_router
from finboy.api.v1.connections import router as connections_router
from finboy.api.v1.demo import router as demo_router
from finboy.api.v1.entries import router as entries_router
from finboy.api.v1.health import router as health_router
from finboy.api.v1.imports import router as imports_router
from finboy.api.v1.money import router as money_router
from finboy.api.v1.privacy import router as privacy_router
from finboy.api.v1.readiness import router as readiness_router
from finboy.api.v1.transactions import router as transactions_router
from finboy.api.v1.whatsapp import router as whatsapp_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth_router)
api_router.include_router(health_router)
api_router.include_router(connections_router)
api_router.include_router(imports_router)
api_router.include_router(privacy_router)
api_router.include_router(assistant_router)
api_router.include_router(money_router)
api_router.include_router(budgets_router)
api_router.include_router(transactions_router)
api_router.include_router(entries_router)
api_router.include_router(account_router)

api_router.include_router(whatsapp_router)

api_router.include_router(readiness_router)

api_router.include_router(demo_router)
