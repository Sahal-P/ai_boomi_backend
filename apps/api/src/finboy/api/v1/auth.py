from cryptography.fernet import Fernet
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field, SecretStr
from starlette.responses import JSONResponse

from finboy.core.access import COOKIE, SESSION_SECONDS, authenticated, check_password
from finboy.core.errors import error_response

router = APIRouter(prefix="/auth", tags=["household access"])


class LoginInput(BaseModel):
    password: SecretStr = Field(min_length=1, max_length=256)


@router.get("/session")
def session(request: Request) -> dict[str, bool]:
    return {
        "required": request.app.state.settings.environment == "production",
        "authenticated": authenticated(request),
    }


@router.post("/login")
def login(body: LoginInput, request: Request) -> JSONResponse:
    settings = request.app.state.settings
    if settings.environment != "production":
        return JSONResponse({"authenticated": True})
    if not request.app.state.login_throttle.admit():
        return error_response(request, 429, "try_later", "Please try again in a minute.")
    if not check_password(
        body.password.get_secret_value(), settings.household_password_hash.get_secret_value()
    ):
        return error_response(request, 401, "invalid_credentials", "Unable to sign in.")
    response = JSONResponse({"authenticated": True})
    response.set_cookie(
        COOKIE,
        Fernet(settings.web_session_key.get_secret_value())
        .encrypt(b"finboy:household:v1")
        .decode(),
        max_age=SESSION_SECONDS,
        secure=True,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return response


@router.post("/logout")
def logout() -> JSONResponse:
    response = JSONResponse({"authenticated": False})
    response.delete_cookie(COOKIE, path="/", secure=True, httponly=True, samesite="lax")
    return response
