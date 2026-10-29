"""Plain Hindi copy for pilot households: one idea per line, picture cues, and a spoken twin.

Written for people who may not read comfortably: every card is also read aloud, buttons say
what they do, and amounts appear the way they are said ("₹1,200"). Speech uses only native
script ("फ़िनबॉय", not "FinBoy") so Hindi voices pronounce it.
"""

from datetime import date

from finboy.services.assistant.language import money, spoken_money
from finboy.services.money.budgets import BudgetStatus

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
    'बंद करना हो तो "बंद" लिखिए।\n'
    "English: en · മലയാളം: ml\n\n"
    "क्या आप सहमत हैं?"
)
CONSENT_SPEECH = (
    "नमस्ते! मैं फ़िनबॉय हूँ। आप बोलकर पैसों का हिसाब रख सकते हैं। मैं आपकी आवाज़, फ़ोटो और "
    "संदेश नहीं रखता। सिर्फ़ रकम, तारीख, और किसे दिया, यह लिखता हूँ। सहमत हैं तो हाँ दबाइए।"
)
WELCOME = (
    "धन्यवाद! 🙏\n"
    "अब जो भी खर्च हो या पैसे आएँ, बस भेज दीजिए:\n"
    '✍️ "चाय 20, ऑटो 50, खाना 120"\n'
    '🎤 बोलकर: "दूधवाले को 500 दिए"\n'
    "📸 बिल की फ़ोटो या UPI का स्क्रीनशॉट\n"
    "मैं तुरंत जोड़कर सही श्रेणी में रख दूँगा।\n"
    'महीने का हिसाब देखने के लिए "इस महीने" लिखिए, बजट के लिए "खाने का बजट 5000"।'
)
WELCOME_SPEECH = (
    "धन्यवाद! अब जो भी खर्च हो, बस बताइए, जैसे, दूधवाले को पाँच सौ दिए। मैं तुरंत जोड़ दूँगा। "
    "महीने का हिसाब देखने के लिए इस महीने लिखिए।"
)
DECLINED = 'ठीक है। कुछ भी नहीं रखा गया। मन बदले तो "नमस्ते" लिखिए।'
EXPIRED = "यह बटन अब काम नहीं करता। नया संदेश भेजिए।"
CHANGED = "यह हिसाब पहले ही बदल चुका है। नया संदेश भेजिए।"
UNDO_REFUSED = "अब वापस नहीं हो सकता — उसके बाद कुछ और बदल चुका है।"
CHANGE_ASK = "✏️ सही रकम बोलिए या लिखिए। जैसे: 400"
CHANGE_ASK_SPEECH = "सही रकम बोलिए, जैसे चार सौ।"
AMOUNT_UNCLEAR = "रकम समझ नहीं आई। सिर्फ़ रकम बोलिए या लिखिए, जैसे: 400"
UNAVAILABLE = "अभी यह नहीं हो पाया। थोड़ी देर बाद फिर भेजिए।"
VOICE_UNCLEAR = "आवाज़ साफ़ नहीं आई। फिर से बोलिए या लिखिए।"
ADDED_SPEECH, NOT_ADDED_SPEECH = "जोड़ दिया।", "नहीं जोड़ा।"
REMEMBERED_SPEECH = "याद रख लिया।"
PAID_REPEAT_SPEECH = "जोड़ दिया। अगले महीने भी यही देना है?"
DUE_LABEL = "किस्त"
STOP_REPLY = 'FinBoy के जवाब बंद कर दिए। फिर से शुरू करने के लिए "शुरू" लिखिए।'
START_REPLY = 'FinBoy फिर से शुरू हो गया। बोलकर बताइए, जैसे: "दूधवाले को 500 दिए"।'
LANGUAGE_CHOSEN = 'हिंदी चुन ली। बोलकर बताइए, जैसे: "दूधवाले को 500 दिए"।'


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


# Sign-up and sign-in (docs/signup-round/contract.md).
SIGN_IN_YES, CREATE_YES, LINK_YES = "✅ हाँ, मैं ही हूँ", "✅ हाँ, बनाइए", "✅ हाँ, जोड़िए"
SELF_CONSENT = (
    "नमस्ते! मैं FinBoy हूँ। 🙏\n"
    "बोलकर पैसों का हिसाब रखिए।\n\n"
    "मैं सिर्फ़ यह लिखता हूँ: रकम, तारीख, किसे दिया या किससे मिला, और किस काम के लिए।\n"
    "आपकी आवाज़, फ़ोटो और संदेश नहीं रखता।\n"
    "आपका हिसाब सिर्फ़ आप देख सकते हैं। सब मिटाना हो तो FinBoy वेबसाइट पर "
    "Privacy → Delete my account दबाइए।\n"
    'बंद करना हो तो "बंद" लिखिए।\n'
    "English: en · മലയാളം: ml\n\n"
    "क्या आप सहमत हैं?"
)
FULL = "अभी FinBoy में जगह भर गई है 🙏\nJOIN लिखकर भेजिए, जगह खुलते ही हम बताएँगे।"
JOINED = "✅ आपका नाम सूची में है। जगह खुलते ही यहीं बताएँगे।"
SIGNED_IN = "✅ हो गया। अब ब्राउज़र में FinBoy पर वापस जाइए।"
LINKED = "✅ जुड़ गया। अब ब्राउज़र में FinBoy पर वापस जाइए।"
LOGIN_DECLINED = "ठीक है। किसी को साइन इन नहीं किया गया।"
LOGIN_EXPIRED = "यह कोड पुराना हो गया। FinBoy वेबसाइट पर फिर से शुरू कीजिए।"
WEB_NOT_PILOT = "FinBoy वेबसाइट पायलट का हिस्सा नहीं है। FinBoy यहीं WhatsApp पर इस्तेमाल करते रहिए।"
ALREADY_LINKED = "यह WhatsApp पहले से किसी दूसरे FinBoy खाते से जुड़ा है, इसलिए नहीं जुड़ सकता।"
USAGE_LIMIT = "आज आपने FinBoy बहुत इस्तेमाल किया 🙏 कल फिर कोशिश कीजिए।"
SAFETY = (
    "हाँ तभी दबाइए जब आपने अभी-अभी खुद FinBoy वेबसाइट पर यह शुरू किया हो। किसी और का दिया कोड कभी न भेजिए।"
)


def sign_in_card(device: str) -> str:
    return f"🔐 {device} पर FinBoy में साइन इन करें?\n\n{SAFETY}"


def signup_card(device: str) -> str:
    return f"{SELF_CONSENT}\n\n🔐 खाता बनाकर {device} पर साइन इन करें?\n{SAFETY}"


def link_card(device: str) -> str:
    return f"🔗 यह WhatsApp {device} वाले FinBoy खाते से जोड़ें?\n\n{SAFETY}"


# Saved at once (docs/money-manager-round/contract.md). Buttons and list menus stay within
# WhatsApp's limits: 20 characters for a button, 24 for a list row or section title.
AMOUNT, CATEGORY_BUTTON = "✏️ रकम", "🏷️ श्रेणी"
PUT_BACK, UNDO_ALL, FIX_ONE = "↩️ वापस जोड़ें", "↩️ सब हटाएँ", "✏️ एक बदलें"
CHECKIN_YES, CHECKIN_NO = "🔔 महीने का हिसाब", "🔕 हिसाब बंद करें"
CATEGORY_OPEN, CATEGORY_SECTION = "श्रेणी चुनें", "श्रेणियाँ"
FIX_OPEN, FIX_SECTION = "चुनें", "जोड़ी गई बातें"
ASK_BIG = "💡 रकम बड़ी है, इसलिए पहले एक बार देख लीजिए।\n\n"
ASK_SAME = "⚠️ लगता है यह आप पहले ही जोड़ चुके हैं।\n\n"
CATEGORY_ASK = "🏷️ कौन-सी श्रेणी? सूची से चुनिए या लिखिए, जैसे: राशन"
FIX_ASK = "✏️ कौन-सी बात बदलनी है?"
NOTHING_TO_FIX = "ये बातें पहले ही बदल चुकी हैं। नया संदेश भेजिए।"
PUT_BACK_DONE = "↩️ वापस जोड़ दिया।"
AMOUNT_CHANGED = "✏️ रकम बदल दी।"
REMOVED_SPEECH = "हटा दिया।"
TOTAL = "कुल खर्च"


def label(category: str) -> str:
    return TOTAL if category == "total" else CATEGORY.get(category, CATEGORY["other"])


def budget_line(status: BudgetStatus) -> str:
    """🟢 सीमा के 80% से कम, 🟡 80% से, 🔴 सीमा पार होने पर।"""
    spent, limit = money(status.spent_minor), money(status.limit_minor)
    name = label(status.category)
    if status.level == "over":
        over = money(status.spent_minor - status.limit_minor)
        return f"🔴 {name}: {spent} / {limit} — इस महीने {over} ज़्यादा"
    if status.level == "near":
        left = money(status.limit_minor - status.spent_minor)
        return f"🟡 {name}: {spent} / {limit} — इस महीने {left} बाकी"
    return f"🟢 {name}: {spent} / {limit} इस महीने"


def _budget_speech(status: BudgetStatus | None) -> str:
    if status is None or status.level == "ok":
        return ""
    return " बजट से ज़्यादा हो गया।" if status.level == "over" else " बजट पूरा होने वाला है।"


def saved(
    *,
    amount_minor: int,
    out: bool,
    counterparty: str | None,
    day: date,
    category: str,
    today: date,
    budget: BudgetStatus | None,
) -> tuple[str, str]:
    """जोड़ी गई बात (लिखकर) और उसका बोला हुआ रूप।"""
    verb = "दिए" if out else "मिले"
    lines = [f"✅ जोड़ दिया: {money(amount_minor)} {verb}", f"🏷️ {label(category)}"]
    if counterparty:
        lines.append(f"👤 {counterparty}")
    lines.append(f"📅 {day_label(day, today)}")
    if budget is not None:
        lines.append(budget_line(budget))
    speech = f"जोड़ दिया। {spoken_money(amount_minor, 'hi')} {verb}"
    speech += f", {counterparty}।" if counterparty else "।"
    return "\n".join(lines), speech + _budget_speech(budget)


Item = tuple[int, bool, str | None, str]  # रकम, दिए या मिले, किसे, श्रेणी


def _item(item: Item) -> str:
    amount, out, payee, category = item
    return f"• {money(amount)}{'' if out else ' मिले'} · {label(category)}" + (
        f" · {payee}" if payee else ""
    )


def saved_many(
    *, saved: list[Item], unsure: list[Item], budgets: list[BudgetStatus]
) -> tuple[str, str]:
    """एक संदेश की कई बातें: क्या जुड़ा, और क्या एक बार देखना है।"""
    lines = []
    if saved:
        total = sum(amount for amount, _, _, _ in saved)
        lines.append(f"✅ {len(saved)} बातें जोड़ दीं · {money(total)}")
        lines += [_item(item) for item in saved]
    if unsure:
        lines.append("⚠️ अभी नहीं जोड़ा — ✏️ एक बदलें से देखिए:")
        lines += [_item(item) for item in unsure]
    lines += [budget_line(status) for status in budgets]
    speech = f"{len(saved)} बातें जोड़ दीं।" if saved else ""
    if unsure:
        speech += f" {len(unsure)} देखनी हैं।"
    return "\n".join(lines), speech.strip()


def removed(amount_minor: int, out: bool, counterparty: str | None) -> str:
    who = f" · {counterparty}" if counterparty else ""
    return f"↩️ हटा दिया: {money(amount_minor)} {'दिए' if out else 'मिले'}{who}"


def removed_many(count: int, total_minor: int) -> str:
    return f"↩️ {count} बातें हटा दीं ({money(total_minor)})।"


def category_changed(category: str, counterparty: str | None) -> str:
    text = f"🏷️ श्रेणी बदलकर {label(category)} कर दी।"
    return text + (f" अगली बार {counterparty} भी इसी में जाएगा।" if counterparty else "")


TODAY_EMPTY = 'आज अभी कुछ नहीं जुड़ा।\nबस भेज दीजिए, जैसे:\n✍️ "चाय 20, ऑटो 50"'
TODAY_EMPTY_SPEECH = "आज अभी कुछ नहीं जुड़ा।"


def today(*, income: int, outflow: int, count: int, top: list[tuple[str, int]]) -> tuple[str, str]:
    lines = ["📒 आज का हिसाब", f"💸 गए: {money(outflow)} · {count} बातें"]
    if income:
        lines.append(f"💰 आए: {money(income)}")
    if top:
        lines.append("🏷️ " + " · ".join(f"{label(c)} {money(a)}" for c, a in top))
    return "\n".join(lines), f"आज {spoken_money(outflow, 'hi')} गए।"


MONTH_EMPTY = (
    "इस महीने अभी कुछ नहीं जुड़ा।\nबस भेज दीजिए, जैसे:\n"
    '✍️ "चाय 20, ऑटो 50"\n🎤 "दूधवाले को 500 दिए"\n📸 बिल की फ़ोटो'
)
MONTH_EMPTY_SPEECH = "इस महीने अभी कुछ नहीं जुड़ा।"
PLAN_HINT = '🎯 बजट रखिए: "खाने का बजट 5000" · बचत: "हर महीने 5000 बचाना है"'


def goal_line(goal_minor: int, saved_minor: int, income_minor: int) -> str:
    if not income_minor:
        return (
            f"🎯 बचत का लक्ष्य {money(goal_minor)} महीना — देखने के लिए आमदनी जोड़िए, "
            'जैसे: "तनख़्वाह 30000 आई"'
        )
    if saved_minor >= goal_minor:
        return f"💚 बचत {money(saved_minor)} — {money(goal_minor)} का लक्ष्य पूरा ✅"
    if saved_minor < 0:
        return f"💸 आमदनी से {money(-saved_minor)} ज़्यादा खर्च हुआ — लक्ष्य {money(goal_minor)}"
    gap = money(goal_minor - saved_minor)
    return f"🎯 बचत {money(saved_minor)} / लक्ष्य {money(goal_minor)} — {gap} और"


def month(
    *,
    month: int,
    income: int,
    outflow: int,
    saved: int,
    goal: int | None,
    top: list[tuple[str, int]],
    budgets: list[BudgetStatus],
    dues: list[tuple[int, str, date]],
    waiting: int,
) -> tuple[str, str]:
    """इस महीने अब तक: आए, गए, कहाँ गए, बजट, बचत का लक्ष्य, आगे के बिल।"""
    lines = [f"📒 {MONTHS[month - 1]} का हिसाब (अब तक)", f"💰 आए: {money(income)}"]
    lines.append(f"💸 गए: {money(outflow)}")
    if top:
        lines.append("🏷️ सबसे ज़्यादा: " + " · ".join(f"{label(c)} {money(a)}" for c, a in top))
    lines += [budget_line(status) for status in budgets[:4]]
    if goal:
        lines.append(goal_line(goal, saved, income))
    elif not budgets:
        lines.append(PLAN_HINT)
    lines += [f"📌 आगे देना है: {money(a)} · {name} · {date_label(day)}" for a, name, day in dues]
    if waiting:
        lines.append(f"⏳ {waiting} बातें देखनी हैं — उनके संदेश में ✅ हाँ दबाइए।")
    speech = f"इस महीने {spoken_money(income, 'hi')} आए, {spoken_money(outflow, 'hi')} गए।"
    if any(status.level == "over" for status in budgets):
        speech += " एक बजट पार हो गया।"
    return "\n".join(lines), speech


def budget_set(status: BudgetStatus) -> str:
    return (
        f"🎯 बजट रख दिया: {label(status.category)} {money(status.limit_minor)} महीना।\n"
        + budget_line(status)
    )


def budget_removed(category: str) -> str:
    return f"🎯 बजट हटा दिया: {label(category)}।"


def goal_set(goal_minor: int) -> str:
    return f"🎯 बचत का लक्ष्य रख दिया: हर महीने {money(goal_minor)}।"


BUDGET_SET_SPEECH = "बजट रख दिया।"
GOAL_SET_SPEECH = "बचत का लक्ष्य रख दिया।"
GOAL_REMOVED = "🎯 बचत का लक्ष्य हटा दिया।"
CHECKIN_ASK = "🔔 हर महीने की 1 तारीख को ऐसा छोटा हिसाब भेजूँ?"
CHECKIN_ON = "🔔 ठीक है। हर महीने की 1 तारीख को पिछले महीने का हिसाब यहीं भेजूँगा।"
CHECKIN_OFF = "🔕 ठीक है, महीने का हिसाब अब नहीं भेजूँगा।"
