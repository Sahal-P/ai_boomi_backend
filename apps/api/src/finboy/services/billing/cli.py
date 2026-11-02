"""Operator CLI for FinBoy Premium. Prints IDs, dates and counts only, never contact details.

python -m finboy.services.billing.cli run
python -m finboy.services.billing.cli status <household-uuid>
python -m finboy.services.billing.cli grant <household-uuid> --days 30
python -m finboy.services.billing.cli reconcile <txnid>
python -m finboy.services.billing.cli link <household-uuid> --language hi

Locally, prefix each with `uv run --package finboy-api`.
"""

import argparse
import json
import sys
from collections import Counter
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from finboy.core.clock import IST
from finboy.core.config import Settings
from finboy.db.models.billing import BillingPayment
from finboy.db.models.core import User
from finboy.db.session import build_engine
from finboy.services.billing import checkout, links, payu, plans, renewals


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="finboy-billing",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("run", help="reconcile payments and renew AutoPay plans (the timer)")
    status = commands.add_parser("status", help="one household's plan and payment counts")
    status.add_argument("household", type=UUID)
    grant = commands.add_parser("grant", help="add days of Premium without a payment (support)")
    grant.add_argument("household", type=UUID)
    grant.add_argument("--days", type=int, choices=range(1, 367), required=True, metavar="1-366")
    one = commands.add_parser("reconcile", help="ask PayU about one payment now")
    one.add_argument("txnid")
    pay = commands.add_parser("link", help="print a household's 7-day pay link, to send privately")
    pay.add_argument("household", type=UUID)
    pay.add_argument("--language", choices=["en", "hi", "ml"], default="en")
    args = parser.parse_args(argv)

    settings = Settings()
    if not settings.billing_enabled:
        print("Billing is off (BILLING_ENABLED=false); nothing to do.")
        return 0
    engine = build_engine(settings)
    factory = sessionmaker(engine, expire_on_commit=False)
    try:
        with factory() as session:
            if args.command == "run":
                with payu.PayUClient(settings) as client:
                    summary = renewals.run(session, settings, client)
                print(json.dumps(vars(summary)))
            elif args.command == "status":
                plan = plans.plan_for(session, settings, args.household)
                counts = Counter(
                    session.scalars(
                        select(BillingPayment.status).where(
                            BillingPayment.user_id == args.household
                        )
                    )
                )
                print(
                    json.dumps(
                        {
                            "state": plan.state,
                            "trial_ends": _day(plan.trial_ends_at),
                            "paid_through": _day(plan.paid_through),
                            "renewal": plan.renewal,
                            "next_charge_on": str(plan.next_charge_on or "") or None,
                            "payments": dict(counts),
                        }
                    )
                )
            elif args.command == "grant":
                until = renewals.grant(session, args.household, args.days)
                print(f"Premium until {until.astimezone(IST):%d %b %Y %H:%M} IST")
            elif args.command == "link":
                user = session.get(User, args.household)
                if user is None or user.deleted_at is not None or user.pilot:
                    print("No such self-serve household.", file=sys.stderr)
                    return 2
                print(links.link(settings, user.id, user.session_epoch, args.language))
            else:
                if not payu.TXNID.fullmatch(args.txnid):
                    print("Not a FinBoy txnid.", file=sys.stderr)
                    return 2
                with payu.PayUClient(settings) as client:
                    found = checkout.reconcile(session, settings, client, [args.txnid])
                print("PayU knows this payment." if found else "PayU has no such payment yet.")
    finally:
        engine.dispose()
    return 0


def _day(value: object) -> str | None:
    return None if value is None else f"{value.astimezone(IST):%Y-%m-%d}"  # type: ignore[attr-defined]


if __name__ == "__main__":
    raise SystemExit(main())
