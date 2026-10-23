"""Small synchronous Google HTTP adapter; inject Client/transport and sleep in tests."""

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import httpx

from finboy.services.mail.security import MailError

READ_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
INSERT_SCOPE = "https://www.googleapis.com/auth/gmail.insert"
TOKEN_URL = "https://oauth2.googleapis.com/token"
REVOKE_URL = "https://oauth2.googleapis.com/revoke"
GMAIL_URL = "https://gmail.googleapis.com/gmail/v1/users/me"


@dataclass(repr=False)
class GoogleClient:
    client_id: str
    client_secret: str
    redirect_uri: str
    client: httpx.Client = field(default_factory=lambda: httpx.Client(timeout=20))
    sleep: Callable[[float], None] = time.sleep

    def close(self) -> None:
        self.client.close()

    def request(
        self, method: str, url: str, *, retry: bool = True, **kwargs: Any
    ) -> httpx.Response:
        attempts = 4 if retry else 1
        for attempt in range(attempts):
            try:
                response = self.client.request(method, url, **kwargs)
            except httpx.HTTPError:
                if attempt == attempts - 1:
                    raise MailError("gmail_unavailable") from None
            else:
                if response.status_code != 429 and response.status_code < 500:
                    return response
                if attempt == attempts - 1:
                    raise MailError("gmail_unavailable")
            self.sleep(2**attempt)
        raise MailError("gmail_unavailable")

    @staticmethod
    def payload(response: httpx.Response) -> dict[str, Any]:
        try:
            value = response.json()
        except ValueError:
            raise MailError("gmail_unavailable") from None
        if not isinstance(value, dict):
            raise MailError("gmail_unavailable")
        return value

    def exchange(self, code: str, verifier: str) -> dict[str, Any]:
        response = self.request(
            "POST",
            TOKEN_URL,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "redirect_uri": self.redirect_uri,
                "code": code,
                "code_verifier": verifier,
                "grant_type": "authorization_code",
            },
        )
        if response.status_code != 200:
            raise MailError("oauth_failed")
        return self.payload(response)

    def refresh(self, refresh_token: str) -> str:
        response = self.request(
            "POST",
            TOKEN_URL,
            data={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
        )
        payload = self.payload(response)
        if response.status_code == 400 and payload.get("error") == "invalid_grant":
            raise MailError("reconnect_required")
        token = payload.get("access_token")
        if response.status_code != 200 or not isinstance(token, str) or not token:
            raise MailError("gmail_unavailable")
        return token

    def get(
        self, path: str, access_token: str, params: dict[str, str | int] | None = None
    ) -> dict[str, Any]:
        response = self.request(
            "GET",
            f"{GMAIL_URL}/{path}",
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
        )
        if response.status_code == 401:
            raise MailError("reconnect_required")
        if response.status_code != 200:
            raise MailError("gmail_unavailable")
        return self.payload(response)

    def revoke(self, token: str) -> None:
        response = self.request("POST", REVOKE_URL, data={"token": token})
        # Google returns invalid_token when a grant was already revoked.
        if response.status_code == 200:
            return
        if response.status_code == 400 and self.payload(response).get("error") == "invalid_token":
            return
        raise MailError("revoke_failed")
