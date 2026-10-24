"""Customer-facing fact and warning labels for native and romanized styles."""

from finboy.services.assistant.templates import CATEGORY_NAMES

LABELS = {
    "tracked_income_minor": (
        "Tracked income",
        "दर्ज आय",
        "രേഖപ്പെടുത്തിയ വരുമാനം",
        "Recorded aamdani",
        "Record cheytha varumanam",
    ),
    "confirmed_outflows_minor": (
        "Confirmed net spending",
        "पुष्टि किया गया शुद्ध खर्च",
        "സ്ഥിരീകരിച്ച അറ്റ ചെലവ്",
        "Confirmed net kharch",
        "Confirmed net chelavu",
    ),
    "estimated_unallocated_minor": (
        "Estimated unallocated",
        "अनुमानित बची राशि",
        "കണക്കാക്കിയ ബാക്കി തുക",
        "Estimated bachi rakam",
        "Kanakkakkiya baaki thuka",
    ),
    "unresolved_commitments_minor": (
        "Unpaid obligations, including overdue",
        "अवैतनिक और बकाया दायित्व",
        "അടയ്ക്കാത്തതും കുടിശ്ശികയുമായ ബാധ്യതകൾ",
        "Unpaid aur overdue payments",
        "Adakkathathum kudishikayum",
    ),
    "pending_review_count": (
        "Records awaiting review",
        "समीक्षा की प्रतीक्षा में रिकॉर्ड",
        "പരിശോധന കാത്തിരിക്കുന്ന രേഖകൾ",
        "Review ke liye pending records",
        "Review kathirikkunna records",
    ),
    "gross_spending": ("Gross spending", "कुल खर्च", "ആകെ ചെലവ്", "Kul kharch", "Aake chelavu"),
    "refunds": (
        "Refunds and reversals",
        "वापसी और उलटे भुगतान",
        "മടക്കങ്ങളും തിരിച്ചിടലുകളും",
        "Refunds aur reversals",
        "Thirike kittiya thuka",
    ),
    "net_spending": ("Net spending", "शुद्ध खर्च", "അറ്റ ചെലവ്", "Net kharch", "Net chelavu"),
    "income": (
        "Tracked income",
        "दर्ज आय",
        "രേഖപ്പെടുത്തിയ വരുമാനം",
        "Recorded aamdani",
        "Record cheytha varumanam",
    ),
    "outflows": (
        "Confirmed spending",
        "पुष्टि किया गया खर्च",
        "സ്ഥിരീകരിച്ച ചെലവ്",
        "Confirmed kharch",
        "Confirmed chelavu",
    ),
    "upcoming": (
        "Unpaid obligations",
        "अवैतनिक दायित्व",
        "അടയ്ക്കാത്ത ബാധ്യതകൾ",
        "Unpaid payments",
        "Adakkatha badhyathakal",
    ),
    "proposed": (
        "Proposed monthly amount",
        "प्रस्तावित मासिक राशि",
        "നിർദ്ദേശിച്ച പ്രതിമാസ തുക",
        "Proposed monthly rakam",
        "Nirdeshicha monthly thuka",
    ),
    "remaining": (
        "Remaining after proposal",
        "प्रस्ताव के बाद बची राशि",
        "നിർദ്ദേശത്തിനു ശേഷമുള്ള ബാക്കി",
        "Proposal ke baad rakam",
        "Proposal kazhinjulla baaki",
    ),
    "incomplete_coverage": (
        "Email records may be incomplete; this is not your bank balance.",
        "ईमेल रिकॉर्ड अधूरे हो सकते हैं; यह आपका बैंक बैलेंस नहीं है।",
        "ഇമെയിൽ രേഖകൾ അപൂർണ്ണമാകാം; ഇത് ബാങ്ക് ബാലൻസ് അല്ല.",
        "Email records adhoore ho sakte hain; yeh bank balance nahi hai.",
        "Email records apoornnamakam; ithu bank balance alla.",
    ),
    "pending_review_items": (
        "Unreviewed records are excluded.",
        "बिना समीक्षा के रिकॉर्ड गणना से बाहर हैं।",
        "പരിശോധിക്കാത്ത രേഖകൾ കണക്കിൽ ഉൾപ്പെടുത്തിയിട്ടില്ല.",
        "Review ke bina records calculation se bahar hain.",
        "Review cheyyatha records kanakkil illa.",
    ),
    "negative_remaining": (
        "The proposal exceeds tracked available money.",
        "प्रस्ताव दर्ज उपलब्ध राशि से अधिक है।",
        "നിർദ്ദേശം രേഖപ്പെടുത്തിയ ലഭ്യമായ തുകയേക്കാൾ കൂടുതലാണ്.",
        "Proposal tracked available rakam se zyada hai.",
        "Proposal tracked labhyamaya thukayekkal kooduthalanu.",
    ),
    "low_buffer": (
        "Little tracked money remains after this proposal.",
        "प्रस्ताव के बाद दर्ज राशि में बहुत कम बचेगा।",
        "നിർദ്ദേശത്തിനു ശേഷം വളരെ കുറച്ച് രേഖപ്പെടുത്തിയ തുക മാത്രമേ ശേഷിക്കൂ.",
        "Proposal ke baad kam tracked rakam bachegi.",
        "Proposal kazhinju kurachu tracked thuka mathram baaki.",
    ),
}


def local_label(key: str, style: str) -> str:
    index = {"en": 0, "hi": 1, "ml": 2, "hinglish": 3, "manglish": 4}[style]
    if key in LABELS:
        return LABELS[key][index]
    if key in CATEGORY_NAMES:
        names = CATEGORY_NAMES[key]
        return names[index if index < 3 else 0]
    return {
        "en": "Recorded amount",
        "hi": "दर्ज राशि",
        "ml": "രേഖപ്പെടുത്തിയ തുക",
        "hinglish": "Recorded rakam",
        "manglish": "Record cheytha thuka",
    }[style]


def warning_labels(warnings: list[str], style: str) -> dict[str, str]:
    return {key: local_label(key, style) for key in dict.fromkeys(warnings)}
