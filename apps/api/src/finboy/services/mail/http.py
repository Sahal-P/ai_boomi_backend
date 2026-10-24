import logging
from collections.abc import Awaitable, Callable
from http import HTTPStatus

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException
from starlette.responses import Response

from finboy.core.errors import error_response
from finboy.services.mail.security import MailError
from finboy.services.ux.state import TaskError

logger = logging.getLogger(__name__)


def failure(request: Request, exc: MailError) -> JSONResponse:
    status = 409 if exc.code in {"import_busy", "connection_inactive"} else 400
    if exc.code in {
        "gmail_not_configured",
        "gmail_unavailable",
        "revoke_failed",
        "demo_unavailable",
    }:
        status = 503
    elif exc.code == "upload_limit":
        status = 413
    return error_response(request, status, exc.code, "The mail operation could not be completed.")


class MailRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Awaitable[Response]]:
        handler = super().get_route_handler()

        async def safe_handler(request: Request) -> Response:
            try:
                origin = request.headers.get("origin")
                if (
                    request.method in {"POST", "DELETE"}
                    and origin
                    and origin not in request.app.state.settings.allowed_origins
                ):
                    raise HTTPException(403)
                response = await handler(request)
            except MailError as exc:
                response = failure(request, exc)
            except TaskError as exc:
                response = error_response(request, exc.status, exc.code, exc.message)
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
                    request,
                    503,
                    "database_unavailable",
                    "Your source history is currently unavailable.",
                )
            except Exception as exc:
                logger.error("mail.request_failed", extra={"error_type": type(exc).__name__})
                response = error_response(
                    request, 500, "internal_error", "An unexpected error occurred."
                )
            response.headers["Cache-Control"] = "no-store"
            return response

        return safe_handler
