"""Plain Hindi copy for pilot households: one idea per line, picture cues, and a spoken twin.

Written for people who may not read comfortably: every card is also read aloud, buttons say
what they do, and amounts appear the way they are said ("₹1,200"). Speech uses only native
script ("फ़िनबॉय", not "FinBoy") so Hindi voices pronounce it.
"""

from datetime import date

from finboy.services.assistant.language import money, spoken_money

MONTHS = (
    "जनवरी",
    "फ़रवरी",
    "मार्च",
    "अप्रैल",
    "मई",
    "जून",
    "जुलाई",
    "अगस्त",
    "सितंबर",
    "अक्टूबर",
    "नवंबर",
    "दिसंबर",
)
CATEGORY = {
    "salary": "तनख़्वाह",
    "other_income": "दूसरी आमदनी",
    "rent": "किराया",
    "food_dining": "खाना-पीना",
    "groceries": "राशन-किराना",
    "transport": "आना-जाना",
    "shopping": "ख़रीदारी",
    "utilities": "बिजली-पानी",
    "subscriptions": "सदस्यता",
    "travel": "यात्रा",
    "health": "दवा-इलाज",
    "education": "पढ़ाई",
    "investments": "बचत",
    "loan_emi": "कर्ज़ की किस्त",
    "fees": "फ़ीस",
    "transfer": "अपने खाते में",
    "farming": "खेती",
    "livestock": "पशु",
    "phone_recharge": "मोबाइल रिचार्ज",
    "family_events": "शादी-त्योहार",
    "remittance": "परिवार का पैसा",
    "wages": "मज़दूरी",
    "farm_sales": "फ़सल-दूध की बिक्री",
    "govt_benefit": "सरकारी पैसा",
    "other": "दूसरा",
}

# Reply-button titles (Meta allows 20 characters; these stay well under).
YES, CHANGE, NO = "✅ हाँ, सही", "✏️ रकम बदलें", "❌ नहीं"
UNDO = "↩️ वापस लें"
AGREE, DECLINE = "✅ हाँ, मंज़ूर", "❌ नहीं"
PAID, LATER = "✅ भर दिया", "⏰ अभी नहीं"
REMIND, AGAIN = "🔔 हाँ, याद दिलाएँ", "✅ हाँ, अगले महीने"

CONSENT = (
    "नमस्ते! मैं FinBoy हूँ। 🙏\n"
    "बोलकर पैसों का हिसाब रखिए।\n\n"
    "मैं सिर्फ़ यह लिखता हूँ: रकम, तारीख, किसे दिया या किससे मिला, और किस काम के लिए।\n"
    "आपकी आवाज़, फ़ोटो और संदेश नहीं रखता।\n"
    "आपका हिसाब सिर्फ़ इसी नंबर पर दिखेगा। FinBoy की टीम इसे सुरक्षित रखती है।\n"
    "सब मिटवाना हो तो अपने सहायक को बताइए।\n"
    'बंद करना हो तो "बंद" लिखिए।\n\n'
    "क्या आप सहमत हैं?"
)
CONSENT_SPEECH = (
    "नमस्ते! मैं फ़िनबॉय हूँ। आप बोलकर पैसों का हिसाब रख सकते हैं। मैं आपकी आवाज़, फ़ोटो और "
    "संदेश नहीं रखता। सिर्फ़ रकम, तारीख, और किसे दिया, यह लिखता हूँ। सहमत हैं तो हाँ दबाइए।"
)
WELCOME = (
    "धन्यवाद! 🙏\n"
    "अब बोलकर बताइए, जैसे:\n"
    '🎤 "दूधवाले को 500 दिए"\n'
    '🎤 "PM किसान के 2000 आए"\n'
    '🎤 "समूह की किस्त 1200, हर महीने 10 तारीख"\n'
    'सवाल भी पूछ सकते हैं: "इस हफ़्ते कितना खर्च हुआ?"\n'
    'हफ़्ते का हिसाब देखने के लिए "हिसाब" लिखिए।'
)
WELCOME_SPEECH = (
    "धन्यवाद! अब बोलकर बताइए, जैसे, दूधवाले को पाँच सौ दिए। हफ़्ते का हिसाब देखने के लिए हिसाब लिखिए।"
)
DECLINED = 'ठीक है। कुछ भी नहीं रखा गया। मन बदले तो "नमस्ते" लिखिए।'
EXPIRED = "यह बटन अब काम नहीं करता। नया संदेश भेजिए।"
CHANGED = "यह हिसाब पहले ही बदल चुका है। नया संदेश भेजिए।"
UNDO_REFUSED = "अब वापस नहीं हो सकता — उसके बाद कुछ और बदल चुका है।"
CHANGE_ASK = "✏️ सही रकम बोलिए या लिखिए। जैसे: 400"
CHANGE_ASK_SPEECH = "सही रकम बोलिए, जैसे चार सौ।"
AMOUNT_UNCLEAR = "रकम समझ नहीं आई। सिर्फ़ रकम बोलिए या लिखिए, जैसे: 400"
UNAVAILABLE = "अभी यह नहीं हो पाया। थोड़ी देर बाद फिर भेजिए।"


def day_label(day: date, today: date) -> str:
    if day == today:
        return "आज"
    if (today - day).days == 1:
        return "कल"
    return f"{day.day} {MONTHS[day.month - 1]}"


def record_card(
    *,
    amount_minor: int,
    out: bool,
    counterparty: str | None,
    day: date,
    category: str,
    today: date,
) -> tuple[str, str]:
    """The confirm card (text) and its spoken twin."""
    when = day_label(day, today)
    verb = "दिए" if out else "मिले"
    lines = [f"{'💸' if out else '💰'} {money(amount_minor)} {verb}"]
    if counterparty:
        lines.append(f"👤 {counterparty}")
    lines += [f"📅 {when}", f"🏷️ {CATEGORY.get(category, CATEGORY['other'])}", "", "सही है?"]
    lines.append("हाँ दबाने पर ही हिसाब में जुड़ेगा।")
    speech = f"{spoken_money(amount_minor, 'hi')} {verb}"
    speech += f", {counterparty}" if counterparty else ""
    speech += f", {when}। सही है तो हाँ दबाइए।"
    return "\n".join(lines), speech


def confirmed(amount_minor: int, out: bool, counterparty: str | None) -> str:
    who = f" · {counterparty}" if counterparty else ""
    return f"✅ जोड़ दिया: {money(amount_minor)} {'दिए' if out else 'मिले'}{who}"


REJECTED = "❌ नहीं जोड़ा।"
UNDONE = "↩️ वापस ले लिया।"

UNCLEAR = 'समझ नहीं आया। ऐसे बोलिए:\n🎤 "दूधवाले को 500 दिए"\n🎤 "इस हफ़्ते कितना खर्च हुआ?"'
UNCLEAR_SPEECH = "समझ नहीं आया। ऐसे बोलिए, दूधवाले को पाँच सौ दिए।"
AMOUNT_MISSING = 'कितने रुपये? रकम के साथ पूरी बात फिर से बोलिए, जैसे: "दूधवाले को 500 दिए"'
AMOUNT_MISSING_SPEECH = "कितने रुपये? रकम के साथ पूरी बात फिर से बोलिए।"
DUE_DAY_MISSING = 'किस तारीख को देना है? ऐसे बोलिए: "समूह की किस्त 1200, हर महीने 10 तारीख"'
DUE_DAY_MISSING_SPEECH = "किस तारीख को देना है? तारीख के साथ फिर से बोलिए।"
ALREADY = "✅ यह पहले से आपके हिसाब में है।"
BUSY = "अभी पिछला संदेश लिखा जा रहा है। एक मिनट बाद फिर भेजिए।"
REMIND_ASK = "क्या तारीख से पहले WhatsApp पर याद दिलाऊँ?"
REMINDERS_ON = "🔔 ठीक है, तारीख से 2 दिन पहले और उसी दिन याद दिलाऊँगा।"


def date_label(day: date) -> str:
    return f"{day.day} {MONTHS[day.month - 1]}"


def due_card(*, amount_minor: int, label: str, due: date) -> tuple[str, str]:
    """A spoken due, waiting for "हाँ" before it counts or is reminded."""
    text = "\n".join(
        [
            f"📌 {money(amount_minor)} देना है",
            f"🏷️ {label}",
            f"📅 {date_label(due)}",
            "",
            "सही है?",
            "हाँ दबाने पर ही याद रखूँगा।",
        ]
    )
    speech = (
        f"{spoken_money(amount_minor, 'hi')}, {label}, {date_label(due)} को देना है। "
        "सही है तो हाँ दबाइए।"
    )
    return text, speech


def due_saved(amount_minor: int, label: str, due: date) -> str:
    return f"📌 याद रख लिया: {money(amount_minor)} · {label} · {date_label(due)}"


REPEAT_ASK = "अगले महीने भी यही देना है?"
LATER_OK = "ठीक है। भर दें तो ऊपर ✅ भर दिया दबाइए।"
ALREADY_PAID = "✅ यह पहले ही भरा हुआ है।"
OK = "ठीक है।"


def paid_done(amount_minor: int, label: str) -> str:
    return f"✅ {money(amount_minor)} भर दिया — {label} — हिसाब में जोड़ दिया।"


def due_notice(amount_minor: int, label: str, due: date, today: date) -> str:
    """A reminder card: what, how much and when, then the one thing to tap."""
    if due < today:
        when = f"📅 {date_label(due)} को देना था"
    else:
        relative = {0: "आज", 1: "कल", 2: "परसों"}.get((due - today).days)
        when = f"📅 {relative + ', ' if relative else ''}{date_label(due)} — देना है"
    lines = ["📌 याद दिलाना", f"{money(amount_minor)} · {label}", when, "भर दिया हो तो ✅ दबाइए।"]
    return "\n".join(lines)


WEEK_EMPTY = 'इस हफ़्ते अभी कुछ नहीं जुड़ा।\nबोलकर बताइए, जैसे:\n🎤 "दूधवाले को 500 दिए"'
WEEK_EMPTY_SPEECH = "इस हफ़्ते अभी कुछ नहीं जुड़ा। बोलकर बताइए, जैसे, दूधवाले को पाँच सौ दिए।"


def week(
    *,
    income: int,
    outflow: int,
    top: list[tuple[str, int]],
    dues: list[tuple[int, str, date]],
    overdue: int,
    waiting: int,
) -> tuple[str, str]:
    """The reply to हिसाब: this week's money in and out, where it went, and what is due next."""
    lines = ["📒 इस हफ़्ते का हिसाब (सोमवार से आज तक)", f"💰 आए: {money(income)}"]
    lines.append(f"💸 गए: {money(outflow)}")
    names = [(CATEGORY.get(category, CATEGORY["other"]), amount) for category, amount in top]
    if names:
        lines.append("🏷️ सबसे ज़्यादा: " + " · ".join(f"{name} {money(a)}" for name, a in names))
    lines += [f"📌 आगे देना है: {money(a)} · {label} · {date_label(day)}" for a, label, day in dues]
    if overdue:
        lines.append(f"⚠️ तारीख निकल गई, अभी बाकी: {money(overdue)}")
    if waiting:
        lines.append(f"⏳ {waiting} बातें अभी नहीं जुड़ीं — उनके संदेश में ✅ हाँ दबाइए।")
    speech = f"इस हफ़्ते {spoken_money(income, 'hi')} आए, {spoken_money(outflow, 'hi')} गए।"
    if names:
        speech += f" सबसे ज़्यादा {names[0][0]} पर।"
    if dues:
        speech += f" आगे {spoken_money(sum(a for a, _, _ in dues), 'hi')} देने हैं।"
    return "\n".join(lines), speech
