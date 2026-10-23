from io import BytesIO
from unittest.mock import MagicMock

import pytest
from finboy.services.mail.google import INSERT_SCOPE, GoogleClient
from finboy.services.mail.security import MailError
from finboy.services.mail.seed_demo_inbox import one_time_access


@pytest.mark.parametrize("incidental", [None, "/favicon.ico", "/callback?state=tampered&code=bad"])
@pytest.mark.parametrize("denied", [False, True])
def test_seeder_waits_for_valid_callback_after_incidental_connections(
    monkeypatch, incidental, denied
):
    requests = []
    secrets = iter(["expected-state", "expected-verifier"])
    monkeypatch.setattr("finboy.services.mail.seed_demo_inbox.random_secret", lambda: next(secrets))
    monkeypatch.setattr("finboy.services.mail.seed_demo_inbox.webbrowser.open", lambda _: True)

    class FakeServer:
        def __init__(self, _address, callback):
            self.callback = callback

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            pass

        def handle_request(self):
            path = (
                incidental
                if not requests
                else (
                    "/callback?state=expected-state&"
                    + ("error=access_denied" if denied else "code=SYNTHETIC_CODE")
                )
            )
            requests.append(path)
            if path is None:
                return  # Empty browser preconnect; no HTTP request to dispatch.
            handler = object.__new__(self.callback)
            handler.path = path
            handler.send_error = MagicMock()
            handler.send_response = MagicMock()
            handler.send_header = MagicMock()
            handler.end_headers = MagicMock()
            handler.wfile = BytesIO()
            handler.do_GET()

    monkeypatch.setattr("finboy.services.mail.seed_demo_inbox.HTTPServer", FakeServer)
    google = MagicMock(spec=GoogleClient)
    google.client_id = "synthetic-client"
    google.redirect_uri = "http://127.0.0.1:8767/callback"
    google.exchange.return_value = {"scope": INSERT_SCOPE, "access_token": "SYNTHETIC_ACCESS"}
    if denied:
        with pytest.raises(MailError, match="consent_denied"):
            one_time_access(google)
        google.exchange.assert_not_called()
    else:
        assert one_time_access(google) == "SYNTHETIC_ACCESS"
        google.exchange.assert_called_once_with("SYNTHETIC_CODE", "expected-verifier")
    assert len(requests) == 2
