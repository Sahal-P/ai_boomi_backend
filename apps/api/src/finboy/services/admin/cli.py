"""Admin accounts, managed on the server (docs/admin-round/contract.md).

Passwords are asked for without echo and never accepted as arguments, so they stay out of shell
history and process lists. `--password-stdin` exists for CI and tests only.

uv run --package finboy-api python -m finboy.services.admin.cli create --email you@example.com
uv run --package finboy-api python -m finboy.services.admin.cli list
uv run --package finboy-api python -m finboy.services.admin.cli disable --email you@example.com
uv run --package finboy-api python -m finboy.services.admin.cli enable --email you@example.com
uv run --package finboy-api python -m finboy.services.admin.cli reset-password --email you@…
"""

import argparse
import getpass
import sys
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from finboy.core.config import Settings
from finboy.core.errors import AccessError
from finboy.db.models.admin import AdminUser
from finboy.db.session import build_engine
from finboy.services.admin import audit, auth


def _password(from_stdin: bool) -> str:
    if from_stdin:
        return sys.stdin.readline().rstrip("\n")
    first = getpass.getpass("New admin password (12-256 characters): ")
    if getpass.getpass("Repeat it: ") != first:
        raise AccessError("confirmation_mismatch")
    return first


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="finboy-admin",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = parser.add_subparsers(dest="command", required=True)
    for name, purpose in (
        ("create", "add an admin account"),
        ("reset-password", "set a new password, unlock the account and end its sessions"),
    ):
        command = commands.add_parser(name, help=purpose)
        command.add_argument("--email", required=True)
        command.add_argument("--password-stdin", action="store_true", help=argparse.SUPPRESS)
    commands.add_parser("list", help="admin emails, status and last sign-in")
    for name, purpose in (
        ("disable", "disable an admin and end their sessions"),
        ("enable", "let a disabled admin sign in again"),
    ):
        commands.add_parser(name, help=purpose).add_argument("--email", required=True)
    args = parser.parse_args(argv)

    engine = build_engine(Settings())
    factory = sessionmaker(engine, expire_on_commit=False)
    now = datetime.now(UTC)
    try:
        with factory() as session:
            if args.command == "list":
                for admin in session.scalars(select(AdminUser).order_by(AdminUser.created_at)):
                    state = "disabled" if admin.disabled_at else "active"
                    seen = (
                        f"{admin.last_login_at:%Y-%m-%d %H:%M} UTC"
                        if admin.last_login_at
                        else "never"
                    )
                    print(f"{admin.email}  {state}  last sign-in {seen}")
                return 0
            if args.command == "create":
                admin = auth.create_admin(
                    session,
                    email=args.email,
                    password=_password(args.password_stdin),
                    created_by=None,
                    must_change_password=False,
                )
                audit.record(
                    session, "admin_created", admin_id=None, admin=str(admin.id), via="server"
                )
                session.commit()
                print(f"Admin created: {admin.email}")
                return 0
            address = auth.normalize_email(args.email)
            admin = session.scalar(
                select(AdminUser).where(AdminUser.email == address).with_for_update()
            )
            if admin is None:
                print("No admin has that email.", file=sys.stderr)
                return 2
            if args.command == "disable":
                auth.disable_admin(session, admin, actor=None, now=now)
                audit.record(
                    session, "admin_disabled", admin_id=None, admin=str(admin.id), via="server"
                )
                message = f"Admin disabled: {admin.email}"
            elif args.command == "enable":
                if not auth.enable_admin(admin):
                    print(f"Already active: {admin.email}")
                    return 0
                audit.record(
                    session, "admin_enabled", admin_id=None, admin=str(admin.id), via="server"
                )
                message = f"Admin enabled: {admin.email}"
            else:
                auth.reset_password(session, admin, _password(args.password_stdin), now)
                audit.record(
                    session,
                    "admin_password_reset",
                    admin_id=None,
                    admin=str(admin.id),
                    via="server",
                )
                message = f"Password reset and sessions ended: {admin.email}"
            session.commit()
            print(message)
            return 0
    except AccessError as error:
        print(f"Refused: {error.message}", file=sys.stderr)
        return 2
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
