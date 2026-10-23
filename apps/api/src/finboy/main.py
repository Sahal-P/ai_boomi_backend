import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from finboy import __version__
from finboy.api.router import api_router
from finboy.core.config import Settings
from finboy.core.errors import register_error_handlers
from finboy.core.logging import configure_logging
from finboy.core.middleware import RequestContextMiddleware
from finboy.db.session import build_engine

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    configure_logging(settings.log_level)
    engine = build_engine(settings)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        logger.info("application.started")
        try:
            yield
        finally:
            engine.dispose()
            logger.info("application.stopped")

    app = FastAPI(title="FinBoy API", version=__version__, lifespan=lifespan)
    app.state.engine = engine
    app.state.settings = settings
    register_error_handlers(app)
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
