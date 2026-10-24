"""Trusted templates; neither models nor email/question text compose financial claims."""

from finboy.core.languages import Language
from finboy.services.assistant.language import money, spoken_money

DISCLAIMER = (
    "This models cash flow from FinBoy's tracked records. "
    "It is not a recommendation to purchase any security."
)
RECORDS_NOTE = "Based on email-derived and confirmed records. Your actual bank balance may differ."

# Each style shares the same engine facts, while speech always uses a native script.
COPY: dict[str, dict[str, str]] = {
    "en": {
        "spending_query": "Confirmed net spending in this period: {value}.",
        "category_spending": "Confirmed net spending for {category} in this period: {value}.",
        "income_query": "Tracked income in this period: {value}.",
        "unallocated_query": "Estimated unallocated amount: {value}.",
        "upcoming_commitments": "Unpaid tracked obligations, including overdue: {value}.",
        "simulation": (
            "Tracked income: {income}. Confirmed net outflows: {outflows}. Upcoming"
            " obligations: {upcoming}. Proposed monthly commitment: {proposed}. "
            "Estimated unallocated amount after the proposal: {remaining}."
        ),
        "merchant_lookup": (
            "Matching confirmed records are shown below. Individual amounts are "
            "evidence, not a calculated merchant total."
        ),
        "pending": "{count} items awaiting confirmation are excluded.",
        "coverage": RECORDS_NOTE,
        "decline": (
            "I cannot recommend a fund, stock, or portfolio. I can explain "
            "bookkeeping concepts or model a monthly commitment against tracked "
            "cash flow."
        ),
        "scope": (
            "I can answer questions about your email-derived ledger, obligations, "
            "and cash-flow simulations."
        ),
        "clarify": (
            "Please specify one monthly rupee amount or a period as YYYY-MM. I can "
            "report confirmed records and model monthly commitments."
        ),
        "empty": "There are no matching confirmed records in this period.",
        "sip": (
            "A SIP is a scheduled periodic investment. A cash-flow simulation "
            "checks how a proposed payment affects tracked available money; it does"
            " not predict returns or recommend a fund."
        ),
        "emi": (
            "An EMI is a scheduled loan instalment. FinBoy treats an upcoming "
            "instalment as an obligation and a confirmed payment according to its "
            "ledger category."
        ),
        "upi": (
            "UPI is a payment system. A payment notification is evidence to "
            "reconcile with other records, not proof of your account's available "
            "funds."
        ),
        "diversification": (
            "Diversification spreads exposure across investments. It does not "
            "remove risk. I can offer neutral education and cash-flow simulations."
        ),
        "index_fund": (
            "An index fund aims to track a specified market index. Fees, tracking "
            "differences, and market risk affect outcomes. I cannot select a fund "
            "for you."
        ),
    },
    "hi": {
        "spending_query": "इस अवधि में पुष्टि किया गया शुद्ध खर्च: {value}।",
        "category_spending": "इस अवधि में {category} पर पुष्टि किया गया शुद्ध खर्च: {value}।",
        "income_query": "इस अवधि में दर्ज आय: {value}।",
        "unallocated_query": "अनुमानित अनावंटित राशि: {value}।",
        "upcoming_commitments": "बकाया सहित अवैतनिक दर्ज दायित्व: {value}।",
        "simulation": (
            "दर्ज आय: {income}। पुष्टि किया गया शुद्ध खर्च: {outflows}। आने वाले "
            "भुगतान: {upcoming}। प्रस्तावित मासिक भुगतान: {proposed}। प्रस्ताव के "
            "बाद अनुमानित अनावंटित राशि: {remaining}।"
        ),
        "merchant_lookup": (
            "संबंधित पुष्टि किए गए रिकॉर्ड नीचे हैं। अलग-अलग राशियाँ साक्ष्य हैं; यह व्यापारी का कुल खर्च नहीं है।"
        ),
        "pending": "पुष्टि की प्रतीक्षा में {count} रिकॉर्ड गणना से बाहर हैं।",
        "coverage": (
            "यह ईमेल से मिले और पुष्टि किए गए रिकॉर्ड पर आधारित है। आपके बैंक खाते "
            "की वास्तविक उपलब्ध राशि अलग हो सकती है।"
        ),
        "decline": (
            "मैं किसी फंड, शेयर या पोर्टफोलियो की सिफारिश नहीं कर सकता। मैं लेखांकन"
            " समझा सकता हूँ या दर्ज नकदी प्रवाह पर मासिक भुगतान का प्रभाव दिखा सकता"
            " हूँ।"
        ),
        "scope": ("मैं ईमेल से मिले लेजर, आने वाले भुगतान और नकदी प्रवाह के बारे में प्रश्नों का उत्तर दे सकता हूँ।"),
        "clarify": (
            "कृपया रुपये में एक मासिक राशि या वर्ष और महीने की अवधि स्पष्ट करें। "
            "मैं पुष्टि किए गए रिकॉर्ड और मासिक भुगतान का मॉडल दिखा सकता हूँ।"
        ),
        "empty": "इस अवधि में संबंधित पुष्टि किए गए रिकॉर्ड नहीं हैं।",
        "sip": (
            "एस आई पी एक नियमित अंतराल पर किया जाने वाला निवेश है। नकदी प्रवाह का "
            "मॉडल दर्ज धन पर प्रस्तावित भुगतान का असर दिखाता है। यह रिटर्न का "
            "अनुमान या फंड की सिफारिश नहीं है।"
        ),
        "emi": (
            "ई एम आई ऋण की नियमित किस्त है। आने वाली किस्त एक दायित्व है और पुष्टि "
            "किया गया भुगतान लेजर में दर्ज होता है।"
        ),
        "upi": (
            "यू पी आई एक भुगतान प्रणाली है। भुगतान की सूचना अन्य रिकॉर्ड से मिलाने "
            "का साक्ष्य है, उपलब्ध धन का प्रमाण नहीं।"
        ),
        "diversification": (
            "विविधीकरण निवेश को अलग-अलग क्षेत्रों में बाँटता है। इससे जोखिम समाप्त "
            "नहीं होता। मैं सामान्य जानकारी और नकदी प्रवाह का मॉडल दे सकता हूँ।"
        ),
        "index_fund": (
            "इंडेक्स फंड किसी बाज़ार सूचकांक का अनुसरण करता है। शुल्क और बाज़ार "
            "जोखिम परिणाम को प्रभावित करते हैं। मैं आपके लिए फंड नहीं चुन सकता।"
        ),
    },
    "ml": {
        "spending_query": "ഈ കാലയളവിലെ സ്ഥിരീകരിച്ച അറ്റ ചെലവ്: {value}.",
        "category_spending": ("ഈ കാലയളവിൽ {category} എന്ന വിഭാഗത്തിലെ സ്ഥിരീകരിച്ച അറ്റ ചെലവ്: {value}."),
        "income_query": "ഈ കാലയളവിൽ രേഖപ്പെടുത്തിയ വരുമാനം: {value}.",
        "unallocated_query": "കണക്കാക്കിയ നീക്കിവയ്ക്കാത്ത തുക: {value}.",
        "upcoming_commitments": "കുടിശ്ശിക ഉൾപ്പെടെയുള്ള അടയ്ക്കാത്ത രേഖപ്പെടുത്തിയ ബാധ്യതകൾ: {value}.",
        "simulation": (
            "രേഖപ്പെടുത്തിയ വരുമാനം: {income}. സ്ഥിരീകരിച്ച അറ്റ ചെലവ്: {outflows}."
            " വരാനിരിക്കുന്ന ബാധ്യതകൾ: {upcoming}. നിർദ്ദേശിച്ച പ്രതിമാസ തുക: "
            "{proposed}. നിർദ്ദേശത്തിനു ശേഷം കണക്കാക്കിയ നീക്കിവയ്ക്കാത്ത തുക: "
            "{remaining}."
        ),
        "merchant_lookup": (
            "ബന്ധപ്പെട്ട സ്ഥിരീകരിച്ച രേഖകൾ താഴെ കാണാം. ഓരോ തുകയും തെളിവാണ്; വ്യാപാരിയുടെ ആകെ ചെലവ് കണക്കാക്കിയിട്ടില്ല."
        ),
        "pending": "സ്ഥിരീകരണത്തിനായി കാത്തിരിക്കുന്ന {count} രേഖകൾ കണക്കിൽ ഉൾപ്പെടുത്തിയിട്ടില്ല.",
        "coverage": (
            "ഇത് ഇമെയിലുകളിൽ നിന്ന് ലഭിച്ചതും സ്ഥിരീകരിച്ചതുമായ രേഖകളെ "
            "അടിസ്ഥാനമാക്കുന്നു. ബാങ്ക് അക്കൗണ്ടിലെ യഥാർത്ഥ ലഭ്യമായ തുക "
            "വ്യത്യാസപ്പെടാം."
        ),
        "decline": (
            "ഒരു ഫണ്ടോ ഓഹരിയോ പോർട്ട്ഫോളിയോയോ നിർദ്ദേശിക്കാൻ എനിക്ക് കഴിയില്ല. "
            "കണക്കെടുപ്പ് വിശദീകരിക്കാനോ രേഖപ്പെടുത്തിയ പണമൊഴുക്കിൽ പ്രതിമാസ "
            "തുകയുടെ സ്വാധീനം കാണിക്കാനോ കഴിയും."
        ),
        "scope": (
            "ഇമെയിലിൽ നിന്നുള്ള കണക്കുകൾ, ബാധ്യതകൾ, പണമൊഴുക്കിന്റെ മാതൃകകൾ "
            "എന്നിവയെക്കുറിച്ചുള്ള ചോദ്യങ്ങൾക്ക് ഉത്തരം നൽകാം."
        ),
        "clarify": (
            "ദയവായി രൂപയിൽ ഒരു പ്രതിമാസ തുകയോ വർഷവും മാസവും ചേർന്ന കാലയളവോ "
            "വ്യക്തമാക്കുക. സ്ഥിരീകരിച്ച രേഖകളും പ്രതിമാസ തുകയുടെ മാതൃകയും "
            "കാണിക്കാം."
        ),
        "empty": "ഈ കാലയളവിൽ ബന്ധപ്പെട്ട സ്ഥിരീകരിച്ച രേഖകളില്ല.",
        "sip": (
            "എസ് ഐ പി നിശ്ചിത ഇടവേളകളിൽ നടത്തുന്ന നിക്ഷേപമാണ്. പണമൊഴുക്കിന്റെ മാതൃക"
            " രേഖപ്പെടുത്തിയ പണത്തിൽ നിർദ്ദേശിച്ച തുകയുടെ സ്വാധീനം കാണിക്കുന്നു. "
            "ഇത് ലാഭം പ്രവചിക്കുകയോ ഫണ്ട് നിർദ്ദേശിക്കുകയോ ചെയ്യുന്നില്ല."
        ),
        "emi": (
            "ഇ എം ഐ വായ്പയുടെ നിശ്ചിത ഗഡുവാണ്. വരാനിരിക്കുന്ന ഗഡു ഒരു ബാധ്യതയും സ്ഥിരീകരിച്ച അടവ് ലെജറിലെ രേഖയുമാണ്."
        ),
        "upi": (
            "യു പി ഐ ഒരു പണമിടപാട് സംവിധാനമാണ്. ഒരു അറിയിപ്പ് മറ്റു രേഖകളുമായി "
            "ഒത്തുനോക്കാനുള്ള തെളിവാണ്; ലഭ്യമായ പണത്തിന്റെ തെളിവല്ല."
        ),
        "diversification": (
            "വൈവിധ്യവൽക്കരണം നിക്ഷേപം വിവിധ മേഖലകളിലായി വിതരണം ചെയ്യുന്നു. ഇത് "
            "അപകടസാധ്യത ഇല്ലാതാക്കുന്നില്ല. പൊതുവിവരവും പണമൊഴുക്കിന്റെ മാതൃകയും "
            "നൽകാം."
        ),
        "index_fund": (
            "ഇൻഡക്സ് ഫണ്ട് ഒരു വിപണി സൂചികയെ പിന്തുടരാൻ ശ്രമിക്കുന്നു. ഫീസും "
            "വിപണിയിലെ അപകടസാധ്യതയും ഫലത്തെ ബാധിക്കും. നിങ്ങൾക്കായി ഫണ്ട് "
            "തിരഞ്ഞെടുക്കാനാവില്ല."
        ),
    },
    "hinglish": {
        "spending_query": "Is period ka confirmed net kharch: {value}.",
        "category_spending": "Is period mein {category} ka confirmed net kharch: {value}.",
        "income_query": "Is period ki recorded income: {value}.",
        "unallocated_query": "Estimated unallocated rakam: {value}.",
        "upcoming_commitments": "Overdue samet unpaid tracked payments: {value}.",
        "simulation": (
            "Recorded income: {income}. Confirmed net kharch: {outflows}. Aane wale"
            " payments: {upcoming}. Proposed monthly payment: {proposed}. Proposal "
            "ke baad estimated unallocated rakam: {remaining}."
        ),
        "merchant_lookup": (
            "Matching confirmed records neeche hain. Yeh individual evidence hai; "
            "merchant ka total calculate nahi kiya gaya."
        ),
        "pending": "Confirmation ke liye pending {count} records calculation se bahar hain.",
        "coverage": (
            "Yeh email-derived aur confirmed records par based hai. Bank mein "
            "actual available rakam alag ho sakti hai."
        ),
        "decline": (
            "Main fund, stock ya portfolio recommend nahi kar sakta. Bookkeeping "
            "samjha sakta hoon ya tracked cash flow par monthly payment model kar "
            "sakta hoon."
        ),
        "scope": (
            "Main email-derived ledger, upcoming payments aur cash-flow simulation "
            "ke sawalon ka jawab de sakta hoon."
        ),
        "clarify": "Ek monthly rupee amount ya YYYY-MM period batayein.",
        "empty": "Is period mein matching confirmed records nahi hain.",
        "sip": (
            "SIP regular interval par investment hai. Cash-flow model proposed "
            "payment ka tracked paise par asar dikhata hai; return prediction ya "
            "fund recommendation nahi."
        ),
        "emi": (
            "EMI loan ki regular instalment hai. Upcoming instalment obligation "
            "hai; confirmed payment ledger mein record hota hai."
        ),
        "upi": (
            "UPI ek payment system hai. Notification reconciliation ka evidence "
            "hai, available paise ka proof nahi."
        ),
        "diversification": (
            "Diversification investments ko alag exposures mein baantta hai. Risk khatam nahi hota."
        ),
        "index_fund": (
            "Index fund market index ko track karta hai. Fees aur market risk "
            "results ko affect karte hain. Main fund select nahi kar sakta."
        ),
    },
    "manglish": {
        "spending_query": "Ee periodile confirmed net chelavu: {value}.",
        "category_spending": "Ee periodil {category} categoryile confirmed net chelavu: {value}.",
        "income_query": "Ee periodil record cheytha varumanam: {value}.",
        "unallocated_query": "Kanakkakkiya neekkivaykkatha thuka: {value}.",
        "upcoming_commitments": "Kudishika ulppedeyulla adakkatha tracked badhyathakal: {value}.",
        "simulation": (
            "Record cheytha varumanam: {income}. Confirmed net chelavu: {outflows}."
            " Varanirikkunna badhyathakal: {upcoming}. Nirdeshicha prathimasa "
            "thuka: {proposed}. Athinu shesham kanakkakkiya neekkivaykkatha thuka: "
            "{remaining}."
        ),
        "merchant_lookup": (
            "Bandhappetta confirmed records thazhe undu. Oro thukayum evidence "
            "aanu; merchant total kanakkakkiyittilla."
        ),
        "pending": "Confirmation kathirikkunna {count} records kanakkil ulppeduthiyittilla.",
        "coverage": (
            "Email-derived confirmed records adisthanamakkiyathanu. Bankile "
            "yathartha labhyamaya thuka vyathyasappedam."
        ),
        "decline": (
            "Fund, stock, portfolio enniva recommend cheyyanavilla. Bookkeeping "
            "vivarikkam allenkil tracked cash flowil monthly payment model cheyyam."
        ),
        "scope": (
            "Email-derived ledger, badhyathakal, cash-flow simulation ennivayekkurichu chodikam."
        ),
        "clarify": "Oru monthly rupee thuka allenkil YYYY-MM period vyakthamakkuka.",
        "empty": "Ee periodil bandhappetta confirmed records illa.",
        "sip": (
            "SIP nischitha idavelakalil nadathunna nikshepam aanu. Cash-flow model "
            "proposed thukayude swadheenam kanikkunnu; labham pravachikkukayo fund "
            "nirdeshikkukayo cheyyunnilla."
        ),
        "emi": (
            "EMI vaypayude nischitha gadu aanu. Varanirikkunna gadu badhyathayum "
            "confirmed payment ledger recordum aanu."
        ),
        "upi": (
            "UPI oru payment system aanu. Notification mattu recordsumayi "
            "othunokkanulla evidence aanu; labhyamaya panathinte proof alla."
        ),
        "diversification": (
            "Diversification nikshepam pala mekhakalil vitharanam cheyyunnu. Risk illathakkunnilla."
        ),
        "index_fund": (
            "Index fund oru market index pinthudaran sramikkunnu. Feesum market "
            "riskum phalathine badhikkum. Fund thiranjedukkanavilla."
        ),
    },
}

for style, merchant, period in [
    (
        "en",
        "Confirmed gross spending: {gross}. Refunds and reversals: {refunds}. "
        "Net spending: {value}.",
        "Which period should I use? Choose today, yesterday, this month, last month, or YYYY-MM.",
    ),
    (
        "hi",
        "पुष्टि किया गया कुल खर्च: {gross}। वापसी और उलटे भुगतान: {refunds}। शुद्ध खर्च: {value}।",
        "कौन सी अवधि चाहिए? आज, बीते कल, इस महीने, पिछले महीने या YYYY-MM चुनें।",
    ),
    (
        "ml",
        "സ്ഥിരീകരിച്ച ആകെ ചെലവ്: {gross}. മടക്കങ്ങളും തിരിച്ചിടലുകളും: {refunds}. അറ്റ ചെലവ്: {value}.",
        "ഏത് കാലയളവ് വേണം? ഇന്ന്, ഇന്നലെ, ഈ മാസം, കഴിഞ്ഞ മാസം അല്ലെങ്കിൽ YYYY-MM തിരഞ്ഞെടുക്കുക.",
    ),
    (
        "hinglish",
        "Confirmed kul kharch: {gross}. Refunds aur reversals: {refunds}. Net kharch: {value}.",
        "Kaunsa period chahiye? Aaj, beeta kal, is mahine, pichle mahine ya YYYY-MM chunein.",
    ),
    (
        "manglish",
        "Confirmed aake chelavu: {gross}. Thirike kittiyathu: {refunds}. Net chelavu: {value}.",
        "Ethu period venam? Innu, innale, ee masam, kazhinja masam "
        "allenkil YYYY-MM thiranjedukkuka.",
    ),
]:
    COPY[style]["merchant_total"] = merchant
    COPY[style]["clarify_period"] = period
for style, text in {
    "en": "Which merchant should I match? Use the name shown in your records.",
    "hi": "किस व्यापारी का खर्च चाहिए? रिकॉर्ड में दिखा नाम बताएं।",
    "ml": "ഏത് വ്യാപാരിയുടെ ചെലവ് വേണം? രേഖകളിലുള്ള പേര് പറയുക.",
    "hinglish": "Kis merchant ka kharch chahiye? Records mein dikhne wala naam batayein.",
    "manglish": "Ethu merchantinte chelavu venam? Recordsilulla peru parayuka.",
}.items():
    COPY[style]["clarify_merchant"] = text


CATEGORY_NAMES: dict[str, tuple[str, str, str]] = {
    "food_dining": ("food and dining", "खाने", "ഭക്ഷണം"),
    "groceries": ("groceries", "किराने", "പലചരക്ക്"),
    "rent": ("rent", "किराये", "വാടക"),
    "transport": ("transport", "परिवहन", "ഗതാഗതം"),
    "shopping": ("shopping", "खरीदारी", "ഷോപ്പിംഗ്"),
    "utilities": ("utilities", "बुनियादी सेवाओं", "അടിസ്ഥാന സേവനങ്ങൾ"),
    "subscriptions": ("subscriptions", "सदस्यताओं", "വരിസംഖ്യ"),
    "travel": ("travel", "यात्रा", "വിനോദയാത്ര"),
    "health": ("health", "स्वास्थ्य", "ആരോഗ്യം"),
    "education": ("education", "शिक्षा", "വിദ്യാഭ്യാസം"),
    "investments": ("investments", "निवेश", "നിക്ഷേപം"),
    "loan_emi": ("loan instalments", "ऋण की किस्तों", "വായ്പാ ഗഡു"),
    "fees": ("fees", "शुल्क", "ഫീസ്"),
    "transfer": ("transfers", "अंतरण", "കൈമാറ്റം"),
    "other": ("other", "अन्य", "മറ്റുള്ളവ"),
    "salary": ("salary", "वेतन", "ശമ്പളം"),
    "other_income": ("other income", "अन्य आय", "മറ്റു വരുമാനം"),
}


def render(
    key: str,
    style: str,
    language: Language,
    *,
    values: dict[str, int] | None = None,
    category: str | None = None,
    count: int = 0,
    speech: bool = False,
) -> str:
    chosen = language if speech else style
    replacements: dict[str, str | int] = {"count": count}
    for name, amount in (values or {}).items():
        replacements[name] = spoken_money(amount, language) if speech else money(amount)
    if category:
        names = CATEGORY_NAMES[category]
        replacements["category"] = names[{"en": 0, "hi": 1, "ml": 2}.get(chosen, 0)]
    return COPY[chosen][key].format(**replacements)


def speech_disclaimer(language: Language) -> str:
    return {
        "en": DISCLAIMER,
        "hi": (
            "यह फ़िनबॉय के दर्ज रिकॉर्ड से नकदी प्रवाह का मॉडल है। यह किसी "
            "प्रतिभूति को खरीदने की सिफारिश नहीं है।"
        ),
        "ml": (
            "ഇത് ഫിൻബോയ് രേഖപ്പെടുത്തിയ കണക്കുകളെ അടിസ്ഥാനമാക്കിയ പണമൊഴുക്കിന്റെ "
            "മാതൃകയാണ്. ഏതെങ്കിലും നിക്ഷേപം വാങ്ങാനുള്ള നിർദ്ദേശമല്ല."
        ),
    }[language]
