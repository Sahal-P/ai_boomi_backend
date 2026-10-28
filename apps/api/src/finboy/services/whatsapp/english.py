"""Plain English copy for the WhatsApp money diary, mirroring `hindi.py` name for name.

Same rules as the Hindi copy: one idea per line, picture cues, buttons that say what they do,
amounts written the way they are said, and a spoken twin for every card.
"""

from datetime import date

from finboy.services.assistant.language import money, spoken_money

MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
CATEGORY = {
    "salary": "Salary",
    "other_income": "Other income",
    "rent": "Rent",
    "food_dining": "Food & dining",
    "groceries": "Groceries",
    "transport": "Transport",
    "shopping": "Shopping",
    "utilities": "Bills (power, water, gas)",
    "subscriptions": "Subscriptions",
    "travel": "Travel",
    "health": "Health",
    "education": "Education",
    "investments": "Savings",
    "loan_emi": "Loan or EMI",
    "fees": "Fees",
    "transfer": "Own account",
    "farming": "Farming",
    "livestock": "Livestock",
    "phone_recharge": "Phone recharge",
    "family_events": "Family events",
    "remittance": "Family money",
    "wages": "Wages",
    "farm_sales": "Farm sales",
    "govt_benefit": "Government money",
    "other": "Other",
}

# Reply-button titles (Meta allows 20 characters; these stay under).
YES, CHANGE, NO = "✅ Yes, correct", "✏️ Change amount", "❌ No"
UNDO = "↩️ Undo"
AGREE, DECLINE = "✅ Yes, I agree", "❌ No"
PAID, LATER = "✅ Paid", "⏰ Not yet"
REMIND, AGAIN = "🔔 Yes, remind me", "✅ Yes, next month"
SIGN_IN_YES, CREATE_YES, LINK_YES = "✅ Yes, it's me", "✅ Yes, create it", "✅ Yes, link it"

CONSENT = (
    "Hi! I'm FinBoy. 🙏\n"
    "Keep track of your money just by talking.\n\n"
    "I only write down: the amount, the date, who you paid or who paid you, and what it was for.\n"
    "I don't keep your voice notes, photos or messages.\n"
    "Only you can see your records. You can delete everything on the FinBoy website "
    "(Privacy → Delete my account).\n"
    'Send "STOP" any time to stop.\n\n'
    "Do you agree?"
)
CONSENT_SPEECH = (
    "Hi! I'm FinBoy. You can keep track of your money just by talking. I don't keep your voice "
    "notes, photos or messages, only the amount, the date and who it was for. If you agree, "
    "tap yes."
)
WELCOME = (
    "Thank you! 🙏\n"
    "Now just tell me, like:\n"
    '🎤 "Paid the milkman 500"\n'
    '🎤 "Got 2000 from PM Kisan"\n'
    '🎤 "Loan instalment 1200, every month on the 10th"\n'
    'You can ask too: "How much did I spend this week?"\n'
    'Send "summary" to see your week.'
)
WELCOME_SPEECH = (
    "Thank you! Now just tell me, like, paid the milkman five hundred. "
    "Send summary to see your week."
)
DECLINED = 'OK. Nothing was kept. If you change your mind, send "Hi".'
EXPIRED = "This button doesn't work any more. Send a new message."
CHANGED = "This record has already changed. Send a new message."
UNDO_REFUSED = "This can't be undone now — something else changed after it."
CHANGE_ASK = "✏️ Say or type the right amount. Like: 400"
CHANGE_ASK_SPEECH = "Say the right amount, like four hundred."
AMOUNT_UNCLEAR = "I didn't get the amount. Say or type just the amount, like: 400"
UNAVAILABLE = "That didn't work right now. Please send it again in a little while."
VOICE_UNCLEAR = "I couldn't hear that clearly. Please say it again or type it."
ADDED_SPEECH, NOT_ADDED_SPEECH = "Added.", "Not added."
REMEMBERED_SPEECH = "I'll remember it."
PAID_REPEAT_SPEECH = "Added. Is the same due next month too?"
DUE_LABEL = "Instalment"
STOP_REPLY = 'FinBoy replies are off. Send "START" to turn them back on.'
START_REPLY = 'FinBoy is back on. Just tell me, like: "Paid the milkman 500".'
LANGUAGE_CHOSEN = 'English it is. Just tell me, like: "Paid the milkman 500".'


def day_label(day: date, today: date) -> str:
    if day == today:
        return "Today"
    if (today - day).days == 1:
        return "Yesterday"
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
    verb = "paid" if out else "received"
    lines = [f"{'💸' if out else '💰'} {money(amount_minor)} {verb}"]
    if counterparty:
        lines.append(f"👤 {counterparty}")
    lines += [f"📅 {when}", f"🏷️ {CATEGORY.get(category, CATEGORY['other'])}", "", "Is this right?"]
    lines.append("It's only added when you tap yes.")
    speech = f"{spoken_money(amount_minor, 'en')} {verb}"
    speech += f", {counterparty}" if counterparty else ""
    speech += f", {when.lower()}. If that's right, tap yes."
    return "\n".join(lines), speech


def confirmed(amount_minor: int, out: bool, counterparty: str | None) -> str:
    who = f" · {counterparty}" if counterparty else ""
    return f"✅ Added: {money(amount_minor)} {'paid' if out else 'received'}{who}"


REJECTED = "❌ Not added."
UNDONE = "↩️ Undone."

UNCLEAR = (
    'I didn\'t understand. Say it like:\n🎤 "Paid the milkman 500"\n'
    '🎤 "How much did I spend this week?"'
)
UNCLEAR_SPEECH = "I didn't understand. Say it like, paid the milkman five hundred."
AMOUNT_MISSING = 'How many rupees? Say it again with the amount, like: "Paid the milkman 500"'
AMOUNT_MISSING_SPEECH = "How many rupees? Say it again with the amount."
DUE_DAY_MISSING = (
    'Which date is it due? Say it like: "Loan instalment 1200, every month on the 10th"'
)
DUE_DAY_MISSING_SPEECH = "Which date is it due? Say it again with the date."
ALREADY = "✅ This is already in your records."
BUSY = "I'm still writing down your last message. Send it again in a minute."
REMIND_ASK = "Shall I remind you on WhatsApp before the date?"
REMINDERS_ON = "🔔 OK, I'll remind you 2 days before and on the day."


def date_label(day: date) -> str:
    return f"{day.day} {MONTHS[day.month - 1]}"


def due_card(*, amount_minor: int, label: str, due: date) -> tuple[str, str]:
    """A spoken due, waiting for "yes" before it counts or is reminded."""
    text = "\n".join(
        [
            f"📌 {money(amount_minor)} to pay",
            f"🏷️ {label}",
            f"📅 {date_label(due)}",
            "",
            "Is this right?",
            "I only remember it when you tap yes.",
        ]
    )
    speech = (
        f"{spoken_money(amount_minor, 'en')}, {label}, due on {date_label(due)}. "
        "If that's right, tap yes."
    )
    return text, speech


def due_saved(amount_minor: int, label: str, due: date) -> str:
    return f"📌 I'll remember: {money(amount_minor)} · {label} · {date_label(due)}"


REPEAT_ASK = "Is the same due next month too?"
LATER_OK = "OK. When you've paid, tap ✅ Paid above."
ALREADY_PAID = "✅ This is already paid."
OK = "OK."


def paid_done(amount_minor: int, label: str) -> str:
    return f"✅ {money(amount_minor)} paid — {label} — added to your records."


def due_notice(amount_minor: int, label: str, due: date, today: date) -> str:
    """A reminder card: what, how much and when, then the one thing to tap."""
    if due < today:
        when = f"📅 Was due on {date_label(due)}"
    else:
        relative = {0: "Today", 1: "Tomorrow", 2: "Day after tomorrow"}.get((due - today).days)
        when = f"📅 {relative + ', ' if relative else ''}{date_label(due)} — to pay"
    lines = ["📌 Reminder", f"{money(amount_minor)} · {label}", when, "If you've paid, tap ✅."]
    return "\n".join(lines)


WEEK_EMPTY = 'Nothing added this week yet.\nJust tell me, like:\n🎤 "Paid the milkman 500"'
WEEK_EMPTY_SPEECH = (
    "Nothing added this week yet. Just tell me, like, paid the milkman five hundred."
)


def week(
    *,
    income: int,
    outflow: int,
    top: list[tuple[str, int]],
    dues: list[tuple[int, str, date]],
    overdue: int,
    waiting: int,
) -> tuple[str, str]:
    """The reply to "summary": money in and out this week, where it went, what is due next."""
    lines = ["📒 This week (Monday to today)", f"💰 In: {money(income)}"]
    lines.append(f"💸 Out: {money(outflow)}")
    names = [(CATEGORY.get(category, CATEGORY["other"]), amount) for category, amount in top]
    if names:
        lines.append("🏷️ Most on: " + " · ".join(f"{name} {money(a)}" for name, a in names))
    lines += [f"📌 Coming up: {money(a)} · {label} · {date_label(day)}" for a, label, day in dues]
    if overdue:
        lines.append(f"⚠️ Past the date, still to pay: {money(overdue)}")
    if waiting:
        lines.append(f"⏳ {waiting} not added yet — tap ✅ Yes on their messages.")
    speech = (
        f"This week {spoken_money(income, 'en')} came in "
        f"and {spoken_money(outflow, 'en')} went out."
    )
    if names:
        speech += f" The most went on {names[0][0].lower()}."
    if dues:
        speech += f" {spoken_money(sum(a for a, _, _ in dues), 'en')} is due soon."
    return "\n".join(lines), speech


# Sign-up and sign-in (docs/signup-round/contract.md).
FULL = "FinBoy is full for now 🙏\nSend JOIN and we'll keep your place in line."
JOINED = "✅ You're on the list. We'll message you here when there's a place."
SIGNED_IN = "✅ Done. Go back to FinBoy in your browser."
LINKED = "✅ Linked. Go back to FinBoy in your browser."
LOGIN_DECLINED = "OK. Nobody was signed in."
LOGIN_EXPIRED = "That code has expired. Start again on the FinBoy website."
WEB_NOT_PILOT = "The FinBoy website isn't part of the pilot. Keep using FinBoy here on WhatsApp."
ALREADY_LINKED = "This WhatsApp already belongs to another FinBoy account, so it can't be linked."
USAGE_LIMIT = "You've used FinBoy a lot today 🙏 Please try again tomorrow."
SAFETY = (
    "Only tap yes if you started this yourself on the FinBoy website just now. "
    "Never send a code that someone else gave you."
)
SELF_CONSENT = (
    "Hi! I'm FinBoy. 🙏\n"
    "Keep track of your money just by talking.\n\n"
    "I only write down: the amount, the date, who you paid or who paid you, and what it was for.\n"
    "I don't keep your voice notes, photos or messages.\n"
    "Only you can see your records. You can delete everything on the FinBoy website "
    "(Privacy → Delete my account).\n"
    'Send "STOP" any time to stop.\n'
    "हिंदी: hi · മലയാളം: ml\n\n"
    "Do you agree?"
)


def sign_in_card(device: str) -> str:
    return f"🔐 Sign in to FinBoy on {device}?\n\n{SAFETY}"


def signup_card(device: str) -> str:
    return f"{SELF_CONSENT}\n\n🔐 Create your account and sign in on {device}?\n{SAFETY}"


def link_card(device: str) -> str:
    return f"🔗 Link this WhatsApp to your FinBoy account on {device}?\n\n{SAFETY}"
