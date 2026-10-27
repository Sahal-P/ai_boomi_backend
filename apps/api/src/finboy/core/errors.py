from http import HTTPStatus

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException


class ProviderUnavailable(Exception):
    """Fixed operational code; provider exception details must never cross this boundary."""

    def __init__(self, code: str = "provider_unavailable") -> None:
        self.code = (
            code
            if code
            in {
                "provider_unavailable",
                "assistant_unavailable",
                "speech_unavailable",
                "configuration_missing",
                "invalid_audio",
            }
            else "provider_unavailable"
        )
        super().__init__(self.code)


class AccessError(Exception):
    """Fixed sign-in and household-access outcomes (docs/signup-round/contract.md)."""

    MESSAGES = {
        "authentication_required": (401, "Please sign in."),
        "web_not_available": (403, "Your household uses FinBoy on WhatsApp."),
        "signups_closed": (403, "FinBoy is full for now. Send JOIN on WhatsApp to join the list."),
        "signup_unavailable": (403, "Sign-up isn't open yet."),
        "sign_in_unavailable": (503, "This way of signing in isn't available right now."),
        "invalid_sign_in": (401, "That sign-in didn't work. Please try again."),
        "login_expired": (410, "That sign-in request has expired. Start again."),
        "login_declined": (403, "The sign-in was declined on WhatsApp."),
        "already_linked": (409, "That account already belongs to another FinBoy household."),
        "usage_limit": (429, "You've reached today's limit. Try again tomorrow."),
        "owner_household": (403, "The owner's household can't be deleted here."),
        "try_later": (429, "Please try again in a minute."),
    }

    def __init__(self, code: str) -> None:
        self.code = code if code in self.MESSAGES else "authentication_required"
        self.status, self.message = self.MESSAGES[self.code]
        super().__init__(self.code)


class ErrorDetail(BaseModel):
    code: str
    message: str
    request_id: str


class ErrorResponse(BaseModel):
    error: ErrorDetail


def error_response(request: Request, status: int, code: str, message: str) -> JSONResponse:
    body = ErrorResponse(
        error=ErrorDetail(code=code, message=message, request_id=request.state.request_id)
    )
    return JSONResponse(status_code=status, content=body.model_dump())


def register_error_handlers(app: FastAPI) -> None:
    from finboy.services.ux.state import TaskError

    @app.exception_handler(TaskError)
    async def handle_task_error(request: Request, exc: TaskError) -> JSONResponse:
        return error_response(request, exc.status, exc.code, exc.message)

    @app.exception_handler(AccessError)
    async def handle_access_error(request: Request, exc: AccessError) -> JSONResponse:
        return error_response(request, exc.status, exc.code, exc.message)

    @app.exception_handler(ProviderUnavailable)
    async def handle_provider_unavailable(
        request: Request, exc: ProviderUnavailable
    ) -> JSONResponse:
        return error_response(request, 503, exc.code, "This service is currently unavailable.")

    @app.exception_handler(HTTPException)
    async def handle_http_error(request: Request, exc: HTTPException) -> JSONResponse:
        # Custom exception detail can contain input; expose only a standard HTTP phrase.
        response = error_response(
            request, exc.status_code, "http_error", HTTPStatus(exc.status_code).phrase
        )
        if exc.headers:
            response.headers.update(exc.headers)
        return response

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, _exc: RequestValidationError
    ) -> JSONResponse:
        return error_response(request, 422, "validation_error", "Request validation failed.")
