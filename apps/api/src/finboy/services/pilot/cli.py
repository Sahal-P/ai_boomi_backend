"""Operator CLI for the village pilot. Prints IDs and counts only, never household content.

uv run --package finboy-api python -m finboy.services.pilot.cli enroll
uv run --package finboy-api python -m finboy.services.pilot.cli owner on|off
uv run --package finboy-api python -m finboy.services.pilot.cli erase <household-uuid> --confirm
uv run --package finboy-api python -m finboy.services.pilot.cli remind
"""

import argparse
import sys
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import sessionmaker

from finboy.core.config import Settings
from finboy.db.session import build_engine
from finboy.services.imports.locking import import_lock
from finboy.services.mail.security import MailError
from finboy.services.pilot import households
from finboy.services.whatsapp import reminders
from finboy.services.whatsapp.config import ChannelUnavailable, channel_config
from finboy.services.whatsapp.meta import MetaClient


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="finboy-pilot",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("enroll", help="create the next pilot household")
    owner = commands.add_parser("owner", help="switch the owner's dogfood pilot flows on or off")
    owner.add_argument("state", choices=["on", "off"])
    erase = commands.add_parser("erase", help="erase one pilot household on request")
    erase.add_argument("household", type=UUID)
    erase.add_argument("--confirm", action="store_true", help="required: erasure is permanent")
    commands.add_parser("remind", help="send due reminder templates (timer; 08:00-20:00 IST)")
    args = parser.parse_args(argv)

    settings = Settings()
    engine = build_engine(settings)
    factory = sessionmaker(engine, expire_on_commit=False)
    try:
        if args.command == "enroll":
            with factory() as session:
                user = households.enroll(session)
            print(f"{user.display_name}: {user.id}")
            print(
                "Add the household's number privately to WHATSAPP_SENDER_ALLOWLIST_JSON with this "
                "ID, register it as a Meta test recipient, then restart FinBoy."
            )
        elif args.command == "owner":
            with factory() as session:
                households.set_owner_pilot(session, enabled=args.state == "on")
            print(f"Owner pilot flows: {args.state}")
        elif args.command == "remind":
            return _remind(settings, factory)
        else:
            if not args.confirm:
                print("Refused: add --confirm to erase this household permanently.")
                return 2
            with import_lock(engine, args.household), factory() as session:
                counts = households.erase(session, args.household)
            print("Erased:", ", ".join(f"{name} {count}" for name, count in counts.items()))
    except households.PilotError as error:
        print(f"Refused: {error.code}")
        return 2
    except MailError:
        print("Refused: an import is running for this household; try again in a minute.")
        return 2
    finally:
        engine.dispose()
    return 0


def _remind(settings: Settings, factory: sessionmaker) -> int:
    try:
        config = channel_config(settings)
    except ChannelUnavailable:
        print("Refused: WhatsApp is not configured.")
        return 2
    client = MetaClient(config)
    try:
        counts = reminders.send_reminders(factory, settings, config, client, datetime.now(UTC))
    finally:
        client.close()
    print("Reminders:", ", ".join(f"{name} {count}" for name, count in counts.items()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
