import logging
from time import perf_counter
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from finboy.core.errors import error_response

logger = logging.getLogger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request.state.request_id = uuid4().hex
        started = perf_counter()
        try:
            response = await call_next(request)
        except Exception as exc:
            # Catch before Uvicorn can print sensitive exception messages or request URLs.
            logger.error(
                "request.failed",
                extra={"request_id": request.state.request_id, "error_type": type(exc).__name__},
            )
            response = error_response(
                request, 500, "internal_error", "An unexpected error occurred."
            )

        response.headers["X-Request-ID"] = request.state.request_id
        logger.info(
            "request.completed",
            extra={
                "request_id": request.state.request_id,
                "method": request.method,
                "route": getattr(request.scope.get("route"), "path", "unmatched"),
                "status_code": response.status_code,
                "duration_ms": round((perf_counter() - started) * 1000, 2),
            },
        )
        return response
