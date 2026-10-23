import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from finboy import __version__
from finboy.api.router import api_router
from finboy.core.access import HouseholdAccessMiddleware, LoginThrottle
from finboy.core.clock import now_ist
from finboy.core.config import Settings
from finboy.core.errors import register_error_handlers
from finboy.core.logging import configure_logging
from finboy.core.middleware import RequestContextMiddleware
from finboy.db.session import build_engine
from finboy.services.whatsapp.receipts import interrupt_stale

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logging(settings.log_level)
    engine = build_engine(settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        logger.info("application.started")
        if settings.whatsapp_enabled:
            try:
                with Session(engine) as session:
                    interrupt_stale(session, before=now_ist() - timedelta(minutes=10))
            except Exception:
                # Readiness remains truthful if database/migrations are unavailable.
                logger.warning("whatsapp.startup_recovery_unavailable")
        try:
            yield
        finally:
            engine.dispose()
            logger.info("application.stopped")

    production = settings.environment == "production"
    app = FastAPI(
        title="FinBoy API",
        version=__version__,
        lifespan=lifespan,
        docs_url=None if production else "/docs",
        redoc_url=None if production else "/redoc",
        openapi_url=None if production else "/openapi.json",
    )
    app.state.engine = engine
    app.state.settings = settings
    app.state.login_throttle = LoginThrottle()
    register_error_handlers(app)
    app.add_middleware(HouseholdAccessMiddleware)
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Accept", "Content-Type"],
        expose_headers=["X-Request-ID"],
    )
    app.include_router(api_router)
    return app
