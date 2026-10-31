"""A Google Pay statement sent as a WhatsApp document: imported like an upload, answered in words.

docs/statement-round/contract.md. The PDF is downloaded from Meta, read in an isolated process and
never stored. The import is the web's: checked against the statement's own totals, saved in one
transaction, matched by UPI transaction ID. WhatsApp never deletes or hand-merges records; removing
an import is on the web, or by the operator for pilot households.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Literal
from uuid import UUID

from sqlalchemy import Engine
from sqlalchemy.orm import sessionmaker

from finboy.core.config import Settings
from finboy.core.languages import Language
from finboy.db.models.mail import ImportRun
from finboy.services.assistant.language import money
from finboy.services.mail.security import MailError, sha256
from finboy.services.money.engine import PeriodSpec
from finboy.services.money.insights import Insights, money_insights
from finboy.services.statements.gpay import StatementError, read_statement
from finboy.services.statements.service import already_imported, run_statement_import, start_import
from finboy.services.statements.views import StatementView, statement_view
from finboy.services.whatsapp.events import InboundQuestion
from finboy.services.whatsapp.meta import InvalidMedia, MetaClient, MetaUnavailable

Outcome = Literal[
    "imported",
    "already_imported",
    "not_statement",
    "locked",
    "unreadable",
    "invalid_file",
    "busy",
    "unavailable",
]
# The receipt keeps only a fixed code; already-imported statements are answered, not failed.
RECEIPT_ERRORS: dict[Outcome, str] = {
    "not_statement": "invalid_document",
    "locked": "invalid_document",
    "unreadable": "invalid_document",
    "invalid_file": "invalid_document",
    "busy": "capture_busy",
    "unavailable": "document_unavailable",
}


@dataclass(frozen=True)
class DocumentImport:
    outcome: Outcome
    statement: StatementView | None = field(default=None, repr=False)
    insights: Insights | None = field(default=None, repr=False)


def import_document(
    engine: Engine,
    settings: Settings,
    client: MetaClient,
    question: InboundQuestion,
    user_id: UUID,
) -> DocumentImport:
    if not settings.statement_import_enabled:
        return DocumentImport("unavailable")
    try:
        data = client.download_document(question.media_id or "", question.mime_type or "").data
    except InvalidMedia:
        return DocumentImport("invalid_file")
    except MetaUnavailable:
        return DocumentImport("unavailable")
    digest = sha256(data)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as session:
        if already_imported(session, user_id, digest):
            return DocumentImport("already_imported")
    try:
        statement = read_statement(data)
    except StatementError as exc:
        return DocumentImport(
            {
                "statement_locked": "locked",
                "not_gpay_statement": "not_statement",
                "upload_limit": "invalid_file",
            }.get(exc.code, "unreadable")  # type: ignore[arg-type]
        )
    with factory() as session:
        try:
            run, holder = start_import(
                session, settings=settings, user_id=user_id, statement=statement, file_sha256=digest
            )
        except MailError as exc:
            return DocumentImport("busy" if exc.code == "import_busy" else "unavailable")
        run_id, queued = run.id, run.status == "queued"
    if not queued:
        # The rows didn't add up to the statement's totals; the failed run shows what was found.
        return DocumentImport("unreadable")
    run_statement_import(engine, run_id, statement, file_sha256=digest, holder=holder)
    with factory() as session:
        run = session.get(ImportRun, run_id)
        view = statement_view(session, run) if run is not None else None
        if run is None or run.status != "completed" or view is None:
            return DocumentImport("unavailable")
        period = PeriodSpec(
            kind="range", start_date=statement.period_start, end_date=statement.period_end
        )
        return DocumentImport(
            "imported", view, money_insights(session, user_id=user_id, period=period)
        )


WORDS: dict[Language, dict[str, str]] = {
    "en": {
        "saved": "Google Pay statement saved ✅",
        "rows": "{rows} payments · {period}",
        "totals": "Paid {paid} and received {received} — both match Google Pay.",
        "new": "{count} new",
        "linked": "{count} already in FinBoy",
        "check": "{count} to check",
        "regular": "Regular payments: about {amount} a month ({names}).",
        "small": "Small payments under ₹200: {amount} a month.",
        "link": "See everything: {url}",
        "already_imported": "This statement is already in FinBoy — nothing was added twice.",
        "not_statement": (
            "That PDF isn't a Google Pay statement. In Google Pay: See transaction history → ⋮ → "
            "Get statement, then send me the PDF."
        ),
        "locked": (
            "That statement has a password. Download it again from Google Pay without one and "
            "send it here."
        ),
        "unreadable": (
            "I couldn't read every row of that statement, so I saved nothing. Download it again "
            "from Google Pay and send it once more."
        ),
        "invalid_file": (
            "I couldn't open that file. Send the Google Pay statement PDF, up to 10 MB — a year or "
            "less at a time."
        ),
        "busy": "I'm still saving your last import. Send the statement again in a minute.",
        "unavailable": "I can't import statements right now. Nothing changed — try again later.",
    },
    "hi": {
        "saved": "Google Pay स्टेटमेंट सेव हो गया ✅",
        "rows": "{rows} भुगतान · {period}",
        "totals": "भेजे {paid}, मिले {received} — दोनों Google Pay से मेल खाते हैं।",
        "new": "{count} नए",
        "linked": "{count} पहले से FinBoy में",
        "check": "{count} जाँचने हैं",
        "regular": "हर महीने के भुगतान: लगभग {amount} महीना ({names})।",
        "small": "₹200 से छोटे भुगतान: {amount} हर महीने।",
        "link": "पूरा देखें: {url}",
        "already_imported": "यह स्टेटमेंट पहले से FinBoy में है — कुछ भी दो बार नहीं जोड़ा गया।",
        "not_statement": (
            "यह PDF Google Pay स्टेटमेंट नहीं है। Google Pay में: See transaction history → ⋮ → "
            "Get statement, फिर PDF यहाँ भेजें।"
        ),
        "locked": "इस स्टेटमेंट पर पासवर्ड है। Google Pay से बिना पासवर्ड के फिर डाउनलोड करके भेजें।",
        "unreadable": (
            "मैं इस स्टेटमेंट की हर लाइन नहीं पढ़ पाया, इसलिए कुछ भी सेव नहीं किया। Google Pay से "
            "फिर डाउनलोड करके भेजें।"
        ),
        "invalid_file": (
            "यह फ़ाइल नहीं खुली। Google Pay स्टेटमेंट की PDF भेजें, 10 MB तक — एक बार में एक साल या कम।"
        ),
        "busy": "पिछला इम्पोर्ट अभी सेव हो रहा है। एक मिनट बाद स्टेटमेंट फिर भेजें।",
        "unavailable": "अभी स्टेटमेंट इम्पोर्ट नहीं हो सकता। कुछ नहीं बदला — बाद में कोशिश करें।",
    },
    "ml": {
        "saved": "Google Pay സ്റ്റേറ്റ്മെന്റ് സേവ് ചെയ്തു ✅",
        "rows": "{rows} പേയ്മെന്റുകൾ · {period}",
        "totals": "അയച്ചത് {paid}, കിട്ടിയത് {received} — രണ്ടും Google Pay-യുമായി ഒത്തുപോകുന്നു.",
        "new": "{count} പുതിയത്",
        "linked": "{count} നേരത്തേ FinBoy-യിൽ ഉണ്ട്",
        "check": "{count} പരിശോധിക്കാൻ",
        "regular": "സ്ഥിരമായ പേയ്മെന്റുകൾ: മാസം ഏകദേശം {amount} ({names}).",
        "small": "₹200-ൽ താഴെയുള്ള പേയ്മെന്റുകൾ: മാസം {amount}.",
        "link": "മുഴുവൻ കാണാൻ: {url}",
        "already_imported": "ഈ സ്റ്റേറ്റ്മെന്റ് നേരത്തേ FinBoy-യിൽ ഉണ്ട് — ഒന്നും രണ്ടുതവണ ചേർത്തില്ല.",
        "not_statement": (
            "ഈ PDF ഒരു Google Pay സ്റ്റേറ്റ്മെന്റ് അല്ല. Google Pay-ൽ: See transaction history → ⋮ → "
            "Get statement, എന്നിട്ട് PDF ഇവിടെ അയയ്ക്കൂ."
        ),
        "locked": (
            "ഈ സ്റ്റേറ്റ്മെന്റിന് പാസ്‌വേഡ് ഉണ്ട്. പാസ്‌വേഡ് ഇല്ലാതെ Google Pay-ൽ നിന്ന് വീണ്ടും ഡൗൺലോഡ് ചെയ്ത് അയയ്ക്കൂ."
        ),
        "unreadable": (
            "ഈ സ്റ്റേറ്റ്മെന്റിലെ എല്ലാ വരികളും വായിക്കാൻ കഴിഞ്ഞില്ല, അതിനാൽ ഒന്നും സേവ് ചെയ്തില്ല. "
            "Google Pay-ൽ നിന്ന് വീണ്ടും ഡൗൺലോഡ് ചെയ്ത് അയയ്ക്കൂ."
        ),
        "invalid_file": (
            "ഈ ഫയൽ തുറക്കാൻ കഴിഞ്ഞില്ല. Google Pay സ്റ്റേറ്റ്മെന്റ് PDF അയയ്ക്കൂ, 10 MB വരെ — ഒരു "
            "തവണ ഒരു വർഷമോ അതിൽ കുറവോ."
        ),
        "busy": "കഴിഞ്ഞ ഇമ്പോർട്ട് ഇപ്പോഴും സേവ് ചെയ്യുന്നു. ഒരു മിനിറ്റിനുശേഷം വീണ്ടും അയയ്ക്കൂ.",
        "unavailable": ("ഇപ്പോൾ സ്റ്റേറ്റ്മെന്റ് ഇമ്പോർട്ട് ചെയ്യാൻ കഴിയില്ല. ഒന്നും മാറിയില്ല — പിന്നീട് ശ്രമിക്കൂ."),
    },
}


def _day(value: date) -> str:
    return f"{value.day}/{value.month}/{value.year}"


def document_reply(result: DocumentImport, language: Language, *, link: str | None) -> str:
    """The import in a few lines; pilot households (no web app) get the facts, not a link."""
    words = WORDS[language]
    view, insights = result.statement, result.insights
    if result.outcome != "imported" or view is None:
        key = "unavailable" if result.outcome == "imported" else result.outcome
        return words[key]
    counts = [
        words["new"].format(count=view.new) if view.new else None,
        words["linked"].format(count=view.linked + view.already_imported)
        if view.linked + view.already_imported
        else None,
        words["check"].format(count=view.possible_duplicates + view.not_counted)
        if view.possible_duplicates + view.not_counted
        else None,
    ]
    lines = [
        words["saved"],
        words["rows"].format(
            rows=view.rows, period=f"{_day(view.period_start)} – {_day(view.period_end)}"
        ),
        words["totals"].format(paid=money(view.paid_minor), received=money(view.got_minor)),
        ", ".join(item for item in counts if item),
    ]
    if insights is not None and insights.regular:
        names = ", ".join(item.name for item in insights.regular[:3])
        lines.append(
            words["regular"].format(amount=money(insights.regular_monthly_minor), names=names)
        )
    if insights is not None and insights.small.count and insights.months > 1:
        lines.append(words["small"].format(amount=money(insights.small.per_month_minor)))
    if link:
        lines.append(words["link"].format(url=link))
    return "\n".join(line for line in lines if line)


def reports_link(settings: Settings, view: StatementView | None) -> str | None:
    if settings.web_app_url is None or view is None:
        return None
    start, end = view.period_start, view.period_end
    return (
        f"{str(settings.web_app_url).rstrip('/')}/reports"
        f"?from={start.year}-{start.month:02}&to={end.year}-{end.month:02}"
    )
