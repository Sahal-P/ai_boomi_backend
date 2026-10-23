"""One-time, insert-only OAuth seeder. Run before connecting the app."""

import argparse
import base64
import json
import os
import secrets
import time
import webbrowser
from email import policy
from email.parser import BytesParser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

from finboy.core.config import Settings
from finboy.services.imports.files import DEMO_DIRECTORY
from finboy.services.mail.google import GMAIL_URL, INSERT_SCOPE, GoogleClient
from finboy.services.mail.security import MailError, pkce_challenge, random_secret, sha256


def read_private_env(path: Path) -> dict[str, str]:
    result = {}
    for line in path.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            result[key.strip()] = value.strip().strip("\"'")
    return result


def one_time_access(google: GoogleClient) -> str:
    state, verifier = random_secret(), random_secret()
    received: dict[str, str] = {}

    class Callback(BaseHTTPRequestHandler):
        def setup(self) -> None:
            super().setup()
            self.connection.settimeout(2)

        def log_message(self, *_args: object) -> None:
            pass

        def do_GET(self) -> None:
            query = parse_qs(urlsplit(self.path).query)
            valid = secrets.compare_digest(query.get("state", [""])[0], state)
            code, error = query.get("code", [""])[0], query.get("error", [""])[0]
            if (
                urlsplit(self.path).path != "/callback"
                or not valid
                or not (code or error)
                or len(code) > 4096
            ):
                self.send_error(400, "Invalid callback")
                return
            received["code"] = code
            received["error"] = error
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(b"FinBoy seeder consent received. You can close this tab.")

    class QuietServer(HTTPServer):
        def handle_error(self, _request: object, _client_address: object) -> None:
            # Browser disconnects/preconnects must never print callback request details.
            pass

    with QuietServer(("127.0.0.1", 8767), Callback) as server:
        server.timeout = 1
        url = "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(
            {
                "client_id": google.client_id,
                "redirect_uri": google.redirect_uri,
                "response_type": "code",
                "scope": INSERT_SCOPE,
                "state": state,
                "code_challenge": pkce_challenge(verifier),
                "code_challenge_method": "S256",
                "access_type": "online",
                "prompt": "consent",
                "include_granted_scopes": "false",
            }
        )
        if not webbrowser.open(url):
            raise MailError("oauth_failed")
        print("Complete the insert-only consent in Chrome using the demo Gmail account.")
        deadline = time.monotonic() + 300
        # Browsers can preconnect or request a favicon before the OAuth callback.
        # Keep listening until a validated callback arrives or the consent window expires.
        while not received and time.monotonic() < deadline:
            server.handle_request()
    if received.get("error") or not received.get("code"):
        raise MailError("consent_denied")
    tokens = google.exchange(received["code"], verifier)
    if set(tokens.get("scope", "").split()) != {INSERT_SCOPE}:
        raise MailError("scope_missing")
    token = tokens.get("access_token")
    if not isinstance(token, str) or not token:
        raise MailError("oauth_failed")
    return token


def seed_messages(
    google: GoogleClient,
    access_token: str,
    *,
    directory: Path,
    manifest_path: Path,
    mailbox_label: str,
) -> tuple[int, int]:
    """Message-ID hashes provide local idempotency without requesting Gmail read access."""
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    namespace = sha256(google.client_id + ":" + mailbox_label)
    seeded = set(manifest.get(namespace, []))
    inserted = skipped = 0
    for path in sorted(directory.glob("*.eml")):
        raw = path.read_bytes()
        message = BytesParser(policy=policy.default).parsebytes(raw)
        message_id = str(message.get("Message-ID", "")).strip()
        if message.get("X-FinBoy-Synthetic") != "1" or not message_id:
            raise MailError("invalid_eml")
        digest = sha256(message_id)
        if digest in seeded:
            skipped += 1
            continue
        response = google.request(
            "POST",
            f"{GMAIL_URL}/messages",
            retry=False,
            params={"internalDateSource": "dateHeader"},
            headers={"Authorization": f"Bearer {access_token}"},
            json={"raw": base64.urlsafe_b64encode(raw).decode(), "labelIds": ["INBOX"]},
        )
        if response.status_code != 200:
            raise MailError("gmail_unavailable")
        seeded.add(digest)
        manifest[namespace] = sorted(seeded)
        manifest_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        temporary = manifest_path.with_suffix(".tmp")
        descriptor = os.open(temporary, os.O_CREAT | os.O_TRUNC | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "w") as handle:
            json.dump(manifest, handle)
        temporary.replace(manifest_path)
        inserted += 1
    return inserted, skipped


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed synthetic demo emails with Gmail insert only"
    )
    parser.add_argument("--directory", type=Path, default=DEMO_DIRECTORY)
    parser.add_argument(
        "--mailbox-label",
        default="demo",
        help="Stable local label; use a different label for each demo account",
    )
    args = parser.parse_args()
    if not list(args.directory.glob("*.eml")):
        parser.error("No rendered .eml fixtures found")
    private = Path.home() / ".config/finboy"
    secrets_file = private / "secrets.env"
    if secrets_file.exists():
        for key, value in read_private_env(secrets_file).items():
            os.environ.setdefault(key, value)
    settings = Settings()
    if not settings.google_oauth_client_id or not settings.google_oauth_client_secret:
        parser.error("Configure Google OAuth credentials first")
    google = GoogleClient(
        settings.google_oauth_client_id,
        settings.google_oauth_client_secret.get_secret_value(),
        "http://127.0.0.1:8767/callback",
    )
    try:
        access = one_time_access(google)
        inserted, skipped = seed_messages(
            google,
            access,
            directory=args.directory,
            manifest_path=private / "gmail-seed-manifest.json",
            mailbox_label=args.mailbox_label,
        )
        print(f"Inserted {inserted} synthetic messages; skipped {skipped} existing Message-IDs.")
    except MailError as exc:
        parser.exit(1, f"Seeder stopped: {exc.code}\n")
    finally:
        google.close()


if __name__ == "__main__":
    main()
