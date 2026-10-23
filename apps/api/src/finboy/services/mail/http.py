from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from finboy.core.errors import error_response
from finboy.services.mail.security import MailError


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
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def safe_handler(request: Request):
            try:
                return await handler(request)
            except MailError as exc:
                return failure(request, exc)

        return safe_handler
