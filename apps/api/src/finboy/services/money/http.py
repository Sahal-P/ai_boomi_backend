"""No-store finance responses with fixed, redacted failures and local write origins."""

import logging
from collections.abc import Awaitable, Callable
from http import HTTPStatus

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.routing import APIRoute
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException
from starlette.responses import Response

from finboy.core.errors import error_response

logger = logging.getLogger(__name__)


class MoneyRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Awaitable[Response]]:
        handler = super().get_route_handler()

        async def safe_handler(request: Request) -> Response:
            try:
                origin = request.headers.get("origin")
                if (
                    request.method in {"POST", "PATCH"}
                    and origin
                    and origin not in request.app.state.settings.allowed_origins
                ):
                    raise HTTPException(403)
                response = await handler(request)
            except HTTPException as exc:
                response = error_response(
                    request, exc.status_code, "http_error", HTTPStatus(exc.status_code).phrase
                )
            except RequestValidationError:
                response = error_response(
                    request, 422, "validation_error", "Request validation failed."
                )
            except SQLAlchemyError:
                response = error_response(
                    request, 503, "database_unavailable", "The ledger is currently unavailable."
                )
            except Exception as exc:
                logger.error("money.request_failed", extra={"error_type": type(exc).__name__})
                response = error_response(
                    request, 500, "internal_error", "An unexpected error occurred."
                )
            response.headers["Cache-Control"] = "no-store"
            return response

        return safe_handler
