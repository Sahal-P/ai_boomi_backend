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
