"""Plain Malayalam copy for the WhatsApp money diary, mirroring `hindi.py` name for name.

Same rules as the Hindi copy: one idea per line, picture cues, buttons that say what they do,
amounts written the way they are said ("₹1,200"), and a spoken twin for every card. Speech
uses only Malayalam script ("ഫിൻബോയ്", not "FinBoy") so the Malayalam voice pronounces it
(docs/malayalam-round/contract.md).
"""

from datetime import date

from finboy.services.assistant.language import money, spoken_money

MONTHS = (
    "ജനുവരി",
    "ഫെബ്രുവരി",
    "മാർച്ച്",
    "ഏപ്രിൽ",
    "മേയ്",
    "ജൂൺ",
    "ജൂലൈ",
    "ഓഗസ്റ്റ്",
    "സെപ്റ്റംബർ",
    "ഒക്ടോബർ",
    "നവംബർ",
    "ഡിസംബർ",
)
CATEGORY = {
    "salary": "ശമ്പളം",
    "other_income": "മറ്റു വരുമാനം",
    "rent": "വാടക",
    "food_dining": "ഭക്ഷണം",
    "groceries": "പലചരക്ക്",
    "transport": "വണ്ടിക്കൂലി",
    "shopping": "ഷോപ്പിംഗ്",
    "utilities": "കറന്റ്, വെള്ളം, ഗ്യാസ്",
    "subscriptions": "സബ്സ്ക്രിപ്ഷൻ",
    "travel": "യാത്ര",
    "health": "മരുന്ന്, ചികിത്സ",
    "education": "പഠനം",
    "investments": "സമ്പാദ്യം",
    "loan_emi": "ലോൺ തവണ",
    "fees": "ഫീസ്",
    "transfer": "സ്വന്തം അക്കൗണ്ടിലേക്ക്",
    "farming": "കൃഷി",
    "livestock": "കന്നുകാലി",
    "phone_recharge": "മൊബൈൽ റീചാർജ്",
    "family_events": "കല്യാണം, ആഘോഷം",
    "remittance": "വീട്ടുകാരുടെ പണം",
    "wages": "കൂലി",
    "farm_sales": "വിളവ് വിൽപ്പന",
    "govt_benefit": "സർക്കാർ സഹായം",
    "other": "മറ്റുള്ളവ",
}

# Reply-button titles (Meta allows 20 characters; these stay under).
YES, CHANGE, NO = "✅ ശരിയാണ്", "✏️ തുക മാറ്റുക", "❌ വേണ്ട"
UNDO = "↩️ തിരിച്ചെടുക്കുക"
AGREE, DECLINE = "✅ സമ്മതം", "❌ വേണ്ട"
PAID, LATER = "✅ അടച്ചു", "⏰ ഇതുവരെ ഇല്ല"
REMIND, AGAIN = "🔔 ഓർമ്മിപ്പിക്കൂ", "✅ അടുത്ത മാസവും"

CONSENT = (
    "നമസ്കാരം! ഞാൻ FinBoy ആണ്. 🙏\n"
    "സംസാരിച്ച് പണത്തിന്റെ കണക്ക് സൂക്ഷിക്കാം.\n\n"
    "ഞാൻ ഇത്ര മാത്രം എഴുതിവയ്ക്കും: തുക, തീയതി, ആർക്ക് കൊടുത്തു അല്ലെങ്കിൽ ആരിൽ നിന്ന് കിട്ടി, "
    "എന്തിനാണ് എന്നത്.\n"
    "നിങ്ങളുടെ ശബ്ദസന്ദേശങ്ങളും ഫോട്ടോകളും മെസേജുകളും ഞാൻ സൂക്ഷിക്കില്ല.\n"
    "നിങ്ങളുടെ കണക്ക് ഈ നമ്പറിൽ മാത്രമേ കാണിക്കൂ. FinBoy ടീം ഇത് സുരക്ഷിതമായി സൂക്ഷിക്കും.\n"
    "എല്ലാം മായ്ക്കണമെങ്കിൽ നിങ്ങളുടെ സഹായിയോട് പറയൂ.\n"
    'നിർത്തണമെങ്കിൽ "നിർത്തുക" എന്ന് അയക്കൂ.\n\n'
    "നിങ്ങൾക്ക് സമ്മതമാണോ?"
)
CONSENT_SPEECH = (
    "നമസ്കാരം! ഞാൻ ഫിൻബോയ് ആണ്. സംസാരിച്ച് നിങ്ങൾക്ക് പണത്തിന്റെ കണക്ക് സൂക്ഷിക്കാം. "
    "നിങ്ങളുടെ ശബ്ദവും ഫോട്ടോകളും മെസേജുകളും ഞാൻ സൂക്ഷിക്കില്ല. തുകയും തീയതിയും ആർക്കാണെന്നും "
    "മാത്രം എഴുതും. സമ്മതമാണെങ്കിൽ സമ്മതം അമർത്തൂ."
)
WELCOME = (
    "നന്ദി! 🙏\n"
    "ഇനി പറഞ്ഞാൽ മതി, ഇങ്ങനെ:\n"
    '🎤 "പാൽക്കാരന് 500 കൊടുത്തു"\n'
    '🎤 "PM കിസാൻ 2000 കിട്ടി"\n'
    '🎤 "ലോൺ തവണ 1200, എല്ലാ മാസവും 10-ാം തീയതി"\n'
    'ചോദിക്കുകയും ചെയ്യാം: "ഈ ആഴ്ച എത്ര ചെലവായി?"\n'
    'ആഴ്ചയിലെ കണക്ക് കാണാൻ "കണക്ക്" എന്ന് അയക്കൂ.'
)
WELCOME_SPEECH = "നന്ദി! ഇനി പറഞ്ഞാൽ മതി, ഇങ്ങനെ, പാൽക്കാരന് അഞ്ഞൂറ് രൂപ കൊടുത്തു. ആഴ്ചയിലെ കണക്ക് കാണാൻ കണക്ക് എന്ന് അയക്കൂ."
DECLINED = 'ശരി. ഒന്നും സൂക്ഷിച്ചിട്ടില്ല. മനസ്സ് മാറിയാൽ "നമസ്കാരം" എന്ന് അയക്കൂ.'
EXPIRED = "ഈ ബട്ടൺ ഇനി പ്രവർത്തിക്കില്ല. പുതിയ മെസേജ് അയക്കൂ."
CHANGED = "ഈ കണക്ക് ഇതിനകം മാറിയിട്ടുണ്ട്. പുതിയ മെസേജ് അയക്കൂ."
UNDO_REFUSED = "ഇനി തിരിച്ചെടുക്കാൻ പറ്റില്ല — അതിനുശേഷം മറ്റൊന്ന് മാറിയിട്ടുണ്ട്."
CHANGE_ASK = "✏️ ശരിയായ തുക പറയൂ അല്ലെങ്കിൽ എഴുതൂ. ഉദാഹരണം: 400"
CHANGE_ASK_SPEECH = "ശരിയായ തുക പറയൂ, ഉദാഹരണത്തിന് നാനൂറ്."
AMOUNT_UNCLEAR = "തുക മനസ്സിലായില്ല. തുക മാത്രം പറയൂ അല്ലെങ്കിൽ എഴുതൂ, ഉദാഹരണം: 400"
UNAVAILABLE = "ഇപ്പോൾ ഇത് നടന്നില്ല. കുറച്ചു കഴിഞ്ഞ് വീണ്ടും അയക്കൂ."
VOICE_UNCLEAR = "ശബ്ദം വ്യക്തമായില്ല. വീണ്ടും പറയൂ അല്ലെങ്കിൽ എഴുതൂ."
ADDED_SPEECH, NOT_ADDED_SPEECH = "ചേർത്തു.", "ചേർത്തില്ല."
REMEMBERED_SPEECH = "ഓർത്തുവച്ചു."
PAID_REPEAT_SPEECH = "ചേർത്തു. അടുത്ത മാസവും ഇതുതന്നെ അടയ്ക്കണോ?"
DUE_LABEL = "തവണ"
STOP_REPLY = 'FinBoy മറുപടികൾ നിർത്തി. വീണ്ടും തുടങ്ങാൻ "തുടങ്ങുക" എന്ന് അയക്കൂ.'
START_REPLY = 'FinBoy വീണ്ടും തുടങ്ങി. പറഞ്ഞാൽ മതി, ഇങ്ങനെ: "പാൽക്കാരന് 500 കൊടുത്തു".'
LANGUAGE_CHOSEN = 'മലയാളം തിരഞ്ഞെടുത്തു. ഇനി പറഞ്ഞാൽ മതി, ഇങ്ങനെ: "പാൽക്കാരന് 500 കൊടുത്തു".'


def day_label(day: date, today: date) -> str:
    if day == today:
        return "ഇന്ന്"
    if (today - day).days == 1:
        return "ഇന്നലെ"
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
    verb = "കൊടുത്തു" if out else "കിട്ടി"
    lines = [f"{'💸' if out else '💰'} {money(amount_minor)} {verb}"]
    if counterparty:
        lines.append(f"👤 {counterparty}")
    lines += [f"📅 {when}", f"🏷️ {CATEGORY.get(category, CATEGORY['other'])}", "", "ശരിയാണോ?"]
    lines.append("ശരിയാണ് അമർത്തിയാൽ മാത്രമേ കണക്കിൽ ചേർക്കൂ.")
    speech = f"{spoken_money(amount_minor, 'ml')} {verb}"
    speech += f", {counterparty}" if counterparty else ""
    speech += f", {when}. ശരിയാണെങ്കിൽ ശരിയാണ് എന്ന് അമർത്തൂ."
    return "\n".join(lines), speech


def confirmed(amount_minor: int, out: bool, counterparty: str | None) -> str:
    who = f" · {counterparty}" if counterparty else ""
    return f"✅ ചേർത്തു: {money(amount_minor)} {'കൊടുത്തു' if out else 'കിട്ടി'}{who}"


REJECTED = "❌ ചേർത്തില്ല."
UNDONE = "↩️ തിരിച്ചെടുത്തു."

UNCLEAR = 'മനസ്സിലായില്ല. ഇങ്ങനെ പറയൂ:\n🎤 "പാൽക്കാരന് 500 കൊടുത്തു"\n🎤 "ഈ ആഴ്ച എത്ര ചെലവായി?"'
UNCLEAR_SPEECH = "മനസ്സിലായില്ല. ഇങ്ങനെ പറയൂ, പാൽക്കാരന് അഞ്ഞൂറ് രൂപ കൊടുത്തു."
AMOUNT_MISSING = 'എത്ര രൂപ? തുകയും ചേർത്ത് വീണ്ടും പറയൂ, ഇങ്ങനെ: "പാൽക്കാരന് 500 കൊടുത്തു"'
AMOUNT_MISSING_SPEECH = "എത്ര രൂപ? തുകയും ചേർത്ത് വീണ്ടും പറയൂ."
DUE_DAY_MISSING = 'ഏത് തീയതിക്കാണ് അടയ്ക്കേണ്ടത്? ഇങ്ങനെ പറയൂ: "ലോൺ തവണ 1200, എല്ലാ മാസവും 10-ാം തീയതി"'
DUE_DAY_MISSING_SPEECH = "ഏത് തീയതിക്കാണ് അടയ്ക്കേണ്ടത്? തീയതിയും ചേർത്ത് വീണ്ടും പറയൂ."
ALREADY = "✅ ഇത് ഇതിനകം നിങ്ങളുടെ കണക്കിലുണ്ട്."
BUSY = "കഴിഞ്ഞ മെസേജ് എഴുതിക്കൊണ്ടിരിക്കുകയാണ്. ഒരു മിനിറ്റ് കഴിഞ്ഞ് വീണ്ടും അയക്കൂ."
REMIND_ASK = "തീയതിക്ക് മുമ്പ് WhatsApp-ൽ ഓർമ്മിപ്പിക്കണോ?"
REMINDERS_ON = "🔔 ശരി, തീയതിക്ക് 2 ദിവസം മുമ്പും അന്നും ഓർമ്മിപ്പിക്കാം."


def date_label(day: date) -> str:
    return f"{day.day} {MONTHS[day.month - 1]}"


def due_card(*, amount_minor: int, label: str, due: date) -> tuple[str, str]:
    """A spoken due, waiting for "ശരിയാണ്" before it counts or is reminded."""
    text = "\n".join(
        [
            f"📌 {money(amount_minor)} അടയ്ക്കണം",
            f"🏷️ {label}",
            f"📅 {date_label(due)}",
            "",
            "ശരിയാണോ?",
            "ശരിയാണ് അമർത്തിയാൽ മാത്രമേ ഓർത്തുവയ്ക്കൂ.",
        ]
    )
    speech = (
        f"{spoken_money(amount_minor, 'ml')}, {label}, {date_label(due)}-ന് അടയ്ക്കണം. "
        "ശരിയാണെങ്കിൽ ശരിയാണ് എന്ന് അമർത്തൂ."
    )
    return text, speech


def due_saved(amount_minor: int, label: str, due: date) -> str:
    return f"📌 ഓർത്തുവച്ചു: {money(amount_minor)} · {label} · {date_label(due)}"


REPEAT_ASK = "അടുത്ത മാസവും ഇതുതന്നെ അടയ്ക്കണോ?"
LATER_OK = "ശരി. അടച്ചുകഴിഞ്ഞാൽ മുകളിലെ ✅ അടച്ചു അമർത്തൂ."
ALREADY_PAID = "✅ ഇത് ഇതിനകം അടച്ചതാണ്."
OK = "ശരി."


def paid_done(amount_minor: int, label: str) -> str:
    return f"✅ {money(amount_minor)} അടച്ചു — {label} — കണക്കിൽ ചേർത്തു."


def due_notice(amount_minor: int, label: str, due: date, today: date) -> str:
    """A reminder card: what, how much and when, then the one thing to tap."""
    if due < today:
        when = f"📅 {date_label(due)}-ന് അടയ്ക്കേണ്ടതായിരുന്നു"
    else:
        relative = {0: "ഇന്ന്", 1: "നാളെ", 2: "മറ്റന്നാൾ"}.get((due - today).days)
        when = f"📅 {relative + ', ' if relative else ''}{date_label(due)} — അടയ്ക്കണം"
    lines = ["📌 ഓർമ്മപ്പെടുത്തൽ", f"{money(amount_minor)} · {label}", when]
    lines.append("അടച്ചെങ്കിൽ ✅ അമർത്തൂ.")
    return "\n".join(lines)


WEEK_EMPTY = 'ഈ ആഴ്ച ഇതുവരെ ഒന്നും ചേർത്തിട്ടില്ല.\nപറഞ്ഞാൽ മതി, ഇങ്ങനെ:\n🎤 "പാൽക്കാരന് 500 കൊടുത്തു"'
WEEK_EMPTY_SPEECH = "ഈ ആഴ്ച ഇതുവരെ ഒന്നും ചേർത്തിട്ടില്ല. പറഞ്ഞാൽ മതി, ഇങ്ങനെ, പാൽക്കാരന് അഞ്ഞൂറ് രൂപ കൊടുത്തു."


def week(
    *,
    income: int,
    outflow: int,
    top: list[tuple[str, int]],
    dues: list[tuple[int, str, date]],
    overdue: int,
    waiting: int,
) -> tuple[str, str]:
    """The reply to "കണക്ക്": this week's money in and out, where it went, what is due next."""
    lines = ["📒 ഈ ആഴ്ചത്തെ കണക്ക് (തിങ്കൾ മുതൽ ഇന്നുവരെ)", f"💰 വന്നത്: {money(income)}"]
    lines.append(f"💸 പോയത്: {money(outflow)}")
    names = [(CATEGORY.get(category, CATEGORY["other"]), amount) for category, amount in top]
    if names:
        lines.append("🏷️ കൂടുതൽ ചെലവായത്: " + " · ".join(f"{name} {money(a)}" for name, a in names))
    lines += [f"📌 വരാനുള്ളത്: {money(a)} · {label} · {date_label(day)}" for a, label, day in dues]
    if overdue:
        lines.append(f"⚠️ തീയതി കഴിഞ്ഞു, ഇനിയും അടയ്ക്കാനുള്ളത്: {money(overdue)}")
    if waiting:
        lines.append(f"⏳ {waiting} എണ്ണം ഇതുവരെ ചേർത്തിട്ടില്ല — അവയുടെ മെസേജിൽ ✅ ശരിയാണ് അമർത്തൂ.")
    speech = f"ഈ ആഴ്ച {spoken_money(income, 'ml')} വന്നു, {spoken_money(outflow, 'ml')} പോയി."
    if names:
        speech += f" ഏറ്റവും കൂടുതൽ ചെലവായത് {names[0][0]}."
    if dues:
        speech += f" ഉടനെ {spoken_money(sum(a for a, _, _ in dues), 'ml')} അടയ്ക്കാനുണ്ട്."
    return "\n".join(lines), speech


# Sign-up and sign-in (docs/signup-round/contract.md).
SIGN_IN_YES, CREATE_YES, LINK_YES = "✅ അതെ, ഞാനാണ്", "✅ അതെ, തുടങ്ങാം", "✅ അതെ, ബന്ധിപ്പിക്കൂ"
SELF_CONSENT = (
    "നമസ്കാരം! ഞാൻ FinBoy ആണ്. 🙏\n"
    "സംസാരിച്ച് പണത്തിന്റെ കണക്ക് സൂക്ഷിക്കാം.\n\n"
    "ഞാൻ ഇത്ര മാത്രം എഴുതിവയ്ക്കും: തുക, തീയതി, ആർക്ക് കൊടുത്തു അല്ലെങ്കിൽ ആരിൽ നിന്ന് കിട്ടി, "
    "എന്തിനാണ് എന്നത്.\n"
    "നിങ്ങളുടെ ശബ്ദസന്ദേശങ്ങളും ഫോട്ടോകളും മെസേജുകളും ഞാൻ സൂക്ഷിക്കില്ല.\n"
    "നിങ്ങളുടെ കണക്ക് നിങ്ങൾക്ക് മാത്രമേ കാണാനാകൂ. എല്ലാം മായ്ക്കാൻ FinBoy വെബ്സൈറ്റിൽ "
    "Privacy → Delete my account അമർത്തൂ.\n"
    'നിർത്തണമെങ്കിൽ "നിർത്തുക" എന്ന് അയക്കൂ.\n'
    "English: en · हिंदी: hi\n\n"
    "നിങ്ങൾക്ക് സമ്മതമാണോ?"
)
FULL = "ഇപ്പോൾ FinBoy-യിൽ സ്ഥലം നിറഞ്ഞു 🙏\nJOIN എന്ന് അയക്കൂ, സ്ഥലം ഒഴിയുമ്പോൾ ഞങ്ങൾ അറിയിക്കാം."
JOINED = "✅ നിങ്ങളുടെ പേര് ലിസ്റ്റിലുണ്ട്. സ്ഥലം ഒഴിയുമ്പോൾ ഇവിടെത്തന്നെ അറിയിക്കാം."
SIGNED_IN = "✅ കഴിഞ്ഞു. ഇനി ബ്രൗസറിലെ FinBoy-യിലേക്ക് തിരിച്ചുപോകൂ."
LINKED = "✅ ബന്ധിപ്പിച്ചു. ഇനി ബ്രൗസറിലെ FinBoy-യിലേക്ക് തിരിച്ചുപോകൂ."
LOGIN_DECLINED = "ശരി. ആരെയും സൈൻ ഇൻ ചെയ്തിട്ടില്ല."
LOGIN_EXPIRED = "ഈ കോഡിന്റെ സമയം കഴിഞ്ഞു. FinBoy വെബ്സൈറ്റിൽ വീണ്ടും തുടങ്ങൂ."
WEB_NOT_PILOT = "FinBoy വെബ്സൈറ്റ് പൈലറ്റിന്റെ ഭാഗമല്ല. ഇവിടെ WhatsApp-ൽ തന്നെ FinBoy ഉപയോഗിക്കുന്നത് തുടരൂ."
ALREADY_LINKED = "ഈ WhatsApp മറ്റൊരു FinBoy അക്കൗണ്ടുമായി ബന്ധിപ്പിച്ചതാണ്, അതുകൊണ്ട് ഇത് ബന്ധിപ്പിക്കാനാകില്ല."
USAGE_LIMIT = "ഇന്ന് നിങ്ങൾ FinBoy ഒരുപാട് ഉപയോഗിച്ചു 🙏 നാളെ വീണ്ടും ശ്രമിക്കൂ."
SAFETY = (
    "നിങ്ങൾ ഇപ്പോൾത്തന്നെ FinBoy വെബ്സൈറ്റിൽ ഇത് തുടങ്ങിയതാണെങ്കിൽ മാത്രം അതെ അമർത്തൂ. "
    "മറ്റാരെങ്കിലും തന്ന കോഡ് ഒരിക്കലും അയക്കരുത്."
)


def sign_in_card(device: str) -> str:
    return f"🔐 FinBoy-യിൽ സൈൻ ഇൻ ചെയ്യണോ? ({device})\n\n{SAFETY}"


def signup_card(device: str) -> str:
    return f"{SELF_CONSENT}\n\n🔐 അക്കൗണ്ട് ഉണ്ടാക്കി സൈൻ ഇൻ ചെയ്യണോ? ({device})\n{SAFETY}"


def link_card(device: str) -> str:
    return f"🔗 ഈ WhatsApp നിങ്ങളുടെ FinBoy അക്കൗണ്ടുമായി ബന്ധിപ്പിക്കണോ? ({device})\n\n{SAFETY}"
