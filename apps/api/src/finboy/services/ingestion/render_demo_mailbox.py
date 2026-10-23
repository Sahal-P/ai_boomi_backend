"""Render synthetic RFC822 messages and an independent oracle from scenario.json."""

import argparse
import calendar
import json
from datetime import date, datetime
from decimal import Decimal
from email.message import EmailMessage
from email.policy import SMTP
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

FIXTURES = Path(__file__).resolve().parents[4] / "fixtures"
MAILBOX = FIXTURES / "demo_mailbox"


def scenario_date(anchor: date, day: int) -> date:
    return anchor.replace(day=min(day, calendar.monthrange(anchor.year, anchor.month)[1]))


def render(anchor: date, output: Path = MAILBOX) -> dict[str, object]:
    scenario = json.loads((MAILBOX / "scenario.json").read_text())
    output.mkdir(parents=True, exist_ok=True)
    expected: list[dict[str, object]] = []
    commitments: list[dict[str, object]] = []
    for index, row in enumerate(scenario["messages"], start=1):
        when = datetime.combine(
            scenario_date(anchor, min(row["day"], anchor.day)), datetime.min.time()
        ).replace(hour=12, minute=5, tzinfo=ZoneInfo("Asia/Kolkata"))
        day = scenario_date(anchor, row["day"]).strftime("%d-%m-%y")
        style = row["style"]
        domain = {
            "bank": "alerts.hdfcbank.test",
            "bill": "bills.local.test",
            "order": "amazon.test",
            "invoice": "amazon.test",
            "noise": "newsletter.test",
        }[style]
        subject = {
            "bank": "Account activity alert",
            "order": "Order confirmation",
            "invoice": "Your invoice",
            "bill": "Your monthly bill",
            "noise": "Information for Arun",
        }[style]
        if style == "noise":
            body = row["body"]
        else:
            amount = Decimal(row["amount_minor"]) / 100
            money = [f"Rs.{amount:,.2f}", f"INR {amount:,.2f}", f"₹{amount:,.2f}"][index % 3]
            merchant, reference, kind = row["merchant"], row["reference"], row["event_type"]
            if style == "bill":
                obligation = "EMI" if kind == "emi_due" else "Bill"
                body = (
                    f"Dear Arun,\n{obligation} amount {money} due {day}; Biller: {merchant};\n"
                    f"Ref: {reference}; Account XX1234.\nDate: {when:%d-%m-%y} 12:05 IST."
                )
                commitments.append(
                    {key: row[key] for key in ("id", "amount_minor", "merchant", "status")}
                    | {"due_date": scenario_date(anchor, row["day"]).isoformat()}
                )
            elif style in {"order", "invoice"}:
                body = (
                    f"Dear Arun,\n{subject}: {money}; Merchant: {merchant};\n"
                    f"Order ID: {reference}; Date: {day} 12:05 IST; card ending 1234.\n"
                    "This confirms the order, not settlement."
                )
            else:
                verb = {
                    "salary": "Salary credited",
                    "debit": "Debited",
                    "refund": "Refund credited",
                    "reversal": "Reversed and credited",
                    "transfer": "Credit-card bill payment debited",
                    "investment": "SIP debited",
                    "failed": "Payment failed",
                }[kind]
                preposition = "from" if kind in {"salary", "refund", "reversal"} else "to"
                instrument = "UPI" if row["id"] == "reviewvpa" else "card"
                body = (
                    f"Dear Arun,\n{verb} {money} {preposition} {merchant} on {day} 12:05 IST;\n"
                    f"A/c XX1234 via {instrument}; UTR: {reference}."
                )
            if "duplicate_of" not in row and style != "bill":
                expected.append(
                    {
                        key: row[key]
                        for key in (
                            "id",
                            "amount_minor",
                            "event_type",
                            "merchant",
                            "category",
                            "status",
                            "review_reason",
                            "linked_to",
                        )
                    }
                    | {
                        "reference_id": reference,
                        "occurred_at": when.isoformat(),
                        "direction": "in"
                        if kind in {"salary", "credit", "refund", "reversal"}
                        else "out",
                        "source_count": 1
                        + sum(
                            other.get("duplicate_of") == row["id"] for other in scenario["messages"]
                        ),
                    }
                )
        message = EmailMessage(policy=SMTP)
        message["From"] = f"FinBoy Synthetic <notify@{domain}>"
        message["To"] = "arun@demo.invalid"
        message["Subject"] = subject
        message["Date"] = when
        message["Message-ID"] = f"<synthetic-{row['id']}@finboy.invalid>"
        message["X-FinBoy-Synthetic"] = "1"
        if row["html"]:
            message.set_content(
                "<html><head><style>.hidden{display:none}</style></head><body>"
                + "".join(f"<p>{escape(line)}</p>" for line in body.splitlines())
                + '<p>Unsubscribe</p><a href="https://tracking.invalid/abc">tracking</a></body></html>',
                subtype="html",
            )
        else:
            message.set_content(
                body + "\n--\nSynthetic service footer https://tracking.invalid/abc\n"
                "> Previous message: INR 9,999 debited\n"
            )
        (output / f"{index:02d}-{row['id']}.eml").write_bytes(message.as_bytes())
    result: dict[str, object] = {
        "anchor": anchor.isoformat(),
        "message_count": len(scenario["messages"]),
        "transactions": expected,
        "commitments": commitments,
        "duplicates_merged": 6,
        "refunds_linked": 3,
        "review_items": 2,
        "income_minor": 6200000,
        "outflows_minor": 3742000,
        "upcoming_minor": 980000,
        "estimated_unallocated_minor": 1478000,
        "categories_after_correction": {
            "rent": 1500000,
            "food_dining": 786000,
            "groceries": 328000,
            "transport": 214000,
            "shopping": 264000,
            "investments": 500000,
            "subscriptions": 150000,
        },
        "correction": {"id": "arya", "field": "category", "old": "travel", "new": "food_dining"},
    }
    (output / "expected_ledger.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--anchor", type=date.fromisoformat, required=True)
    args = parser.parse_args()
    result = render(args.anchor)
    print(json.dumps({"rendered": result["message_count"], "anchor": result["anchor"]}))


if __name__ == "__main__":
    main()
