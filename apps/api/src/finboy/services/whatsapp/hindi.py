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
