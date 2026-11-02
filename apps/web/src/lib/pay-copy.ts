// The WhatsApp pay page in the conversation's language (docs/subscription-round/contract.md).
// The rest of the web app is English; this page is opened from a Hindi or Malayalam chat.

export type PayLanguage = "en" | "hi" | "ml";

const LOCALES: Record<PayLanguage, string> = { en: "en-IN", hi: "hi-IN", ml: "ml-IN" };

export function payDate(value: string, language: PayLanguage): string {
  return new Intl.DateTimeFormat(LOCALES[language], {
    day: "numeric",
    month: "short",
    timeZone: "Asia/Kolkata",
  }).format(new Date(value));
}

export type PayWords = {
  title: string;
  perMonth: string;
  lead: string;
  benefits: [string, string, string, string];
  trial: (date: string) => string;
  next: (date: string) => string;
  email: string;
  phone: string;
  pay: (price: string) => string;
  opening: string;
  secure: string;
  autopay: string;
  allSet: (date: string) => string;
  back: string;
  expired: string;
  loading: string;
  failedTitle: string;
  terms: string;
  refunds: string;
  result: {
    paid: string;
    paidThrough: (date: string) => string;
    autopay: string;
    done: string;
    checking: string;
    confirming: string;
    confirmingDetail: string;
    slow: string;
    failed: string;
    failedDetail: string;
    retry: string;
  };
};

export const PAY_WORDS: Record<PayLanguage, PayWords> = {
  en: {
    title: "FinBoy Premium",
    perMonth: "/ month",
    lead: "Everything FinBoy can do, every day. Cancel any time.",
    benefits: [
      "Voice notes and spoken replies",
      "Answers to any question about your money",
      "Photos of bills and UPI screenshots, read for you",
      "Months of history from a Google Pay statement",
    ],
    trial: (date) => `Your free trial continues until ${date}; your first paid month starts then.`,
    next: (date) => `Your next month starts on ${date}, when this one ends.`,
    email: "Email for receipts",
    phone: "Mobile number",
    pay: (price) => `Pay ${price}`,
    opening: "Opening PayU…",
    secure: "Next: PayU's secure page — UPI, card or net banking.",
    autopay: "Tick AutoPay there to renew by itself; turn it off any time.",
    allSet: (date) => `You're all set — Premium until ${date}.`,
    back: "Back to WhatsApp",
    expired: "This link has expired. Send any message to FinBoy on WhatsApp for a new one.",
    loading: "Loading…",
    failedTitle: "Payment couldn't start",
    terms: "Terms",
    refunds: "Refunds",
    result: {
      paid: "You're on Premium",
      paidThrough: (date) => `Paid through ${date}.`,
      autopay: "AutoPay is on — it renews by itself.",
      done: "Done",
      checking: "Checking your payment…",
      confirming: "Confirming with your bank…",
      confirmingDetail: "This usually takes under a minute. You can go back to WhatsApp — Premium switches on by itself.",
      slow: "Still confirming with your bank. Premium switches on as soon as it does; if money left your account and it doesn't, your bank returns it.",
      failed: "Payment didn't go through",
      failedDetail: "No charge was made. If money left your account, your bank returns it within 5–7 working days.",
      retry: "Try again",
    },
  },
  hi: {
    title: "FinBoy Premium",
    perMonth: "/ महीना",
    lead: "FinBoy की हर सुविधा, हर दिन। कभी भी बंद कर सकते हैं।",
    benefits: [
      "वॉइस नोट और बोलकर जवाब",
      "अपने पैसों के बारे में कोई भी सवाल",
      "बिल की फ़ोटो और UPI स्क्रीनशॉट पढ़कर हिसाब",
      "Google Pay स्टेटमेंट से महीनों का हिसाब",
    ],
    trial: (date) => `आपका मुफ़्त Premium ${date} तक चलेगा; पहला भुगतान वाला महीना उसके बाद शुरू होगा।`,
    next: (date) => `आपका अगला महीना ${date} से शुरू होगा, जब यह ख़त्म होगा।`,
    email: "रसीद के लिए ईमेल",
    phone: "मोबाइल नंबर",
    pay: (price) => `${price} भुगतान करें`,
    opening: "PayU खुल रहा है…",
    secure: "आगे: PayU का सुरक्षित पेज — UPI, कार्ड या नेट बैंकिंग।",
    autopay: "हर महीने अपने-आप भुगतान के लिए वहाँ AutoPay चुनें; कभी भी बंद कर सकते हैं।",
    allSet: (date) => `सब ठीक है — Premium ${date} तक है।`,
    back: "WhatsApp पर वापस जाएँ",
    expired: "यह लिंक पुराना हो गया है। नया लिंक पाने के लिए FinBoy को WhatsApp पर कोई भी संदेश भेजिए।",
    loading: "लोड हो रहा है…",
    failedTitle: "भुगतान शुरू नहीं हो पाया",
    terms: "शर्तें",
    refunds: "रिफ़ंड",
    result: {
      paid: "आपका Premium चालू है",
      paidThrough: (date) => `${date} तक का भुगतान हो गया।`,
      autopay: "AutoPay चालू है — हर महीने अपने-आप भुगतान होगा।",
      done: "ठीक है",
      checking: "आपका भुगतान देख रहे हैं…",
      confirming: "आपके बैंक से पुष्टि हो रही है…",
      confirmingDetail: "आमतौर पर एक मिनट से कम लगता है। आप WhatsApp पर लौट सकते हैं — Premium अपने-आप चालू हो जाएगा।",
      slow: "बैंक से पुष्टि अभी बाकी है। पुष्टि होते ही Premium चालू होगा; अगर पैसा कटा और पुष्टि नहीं हुई, तो बैंक पैसा लौटा देगा।",
      failed: "भुगतान नहीं हो पाया",
      failedDetail: "कोई पैसा नहीं लिया गया। अगर आपके खाते से पैसा कटा है, तो बैंक 5–7 कामकाजी दिनों में लौटा देगा।",
      retry: "फिर से कोशिश करें",
    },
  },
  ml: {
    title: "FinBoy Premium",
    perMonth: "/ മാസം",
    lead: "FinBoy-ന്റെ എല്ലാ സൗകര്യങ്ങളും, എല്ലാ ദിവസവും. എപ്പോൾ വേണമെങ്കിലും നിർത്താം.",
    benefits: [
      "വോയ്സ് നോട്ടുകളും ശബ്ദത്തിലുള്ള മറുപടികളും",
      "നിങ്ങളുടെ പണത്തെക്കുറിച്ചുള്ള ഏത് ചോദ്യത്തിനും മറുപടി",
      "ബില്ലിന്റെ ഫോട്ടോയും UPI സ്ക്രീൻഷോട്ടും വായിച്ച് കണക്ക്",
      "Google Pay സ്റ്റേറ്റ്മെന്റിൽ നിന്ന് മാസങ്ങളുടെ കണക്ക്",
    ],
    trial: (date) => `നിങ്ങളുടെ സൗജന്യ Premium ${date} വരെ തുടരും; ആദ്യ പണമടച്ച മാസം അതിനുശേഷം തുടങ്ങും.`,
    next: (date) => `നിങ്ങളുടെ അടുത്ത മാസം ${date}-ന് തുടങ്ങും, ഇത് തീരുമ്പോൾ.`,
    email: "രസീതിനുള്ള ഇമെയിൽ",
    phone: "മൊബൈൽ നമ്പർ",
    pay: (price) => `${price} അടയ്ക്കൂ`,
    opening: "PayU തുറക്കുന്നു…",
    secure: "അടുത്തത്: PayU-ന്റെ സുരക്ഷിത പേജ് — UPI, കാർഡ് അല്ലെങ്കിൽ നെറ്റ് ബാങ്കിംഗ്.",
    autopay: "എല്ലാ മാസവും സ്വയം പുതുക്കാൻ അവിടെ AutoPay തിരഞ്ഞെടുക്കൂ; എപ്പോൾ വേണമെങ്കിലും നിർത്താം.",
    allSet: (date) => `എല്ലാം ശരിയാണ് — Premium ${date} വരെ ഉണ്ട്.`,
    back: "WhatsApp-ലേക്ക് മടങ്ങൂ",
    expired: "ഈ ലിങ്കിന്റെ കാലാവധി കഴിഞ്ഞു. പുതിയ ലിങ്കിന് FinBoy-ക്ക് WhatsApp-ൽ ഏതെങ്കിലും സന്ദേശം അയക്കൂ.",
    loading: "ലോഡ് ചെയ്യുന്നു…",
    failedTitle: "പേയ്മെന്റ് തുടങ്ങാനായില്ല",
    terms: "നിബന്ധനകൾ",
    refunds: "റീഫണ്ട്",
    result: {
      paid: "നിങ്ങളുടെ Premium ഓണാണ്",
      paidThrough: (date) => `${date} വരെ പണമടച്ചു.`,
      autopay: "AutoPay ഓണാണ് — എല്ലാ മാസവും സ്വയം പുതുക്കും.",
      done: "ശരി",
      checking: "നിങ്ങളുടെ പേയ്മെന്റ് പരിശോധിക്കുന്നു…",
      confirming: "നിങ്ങളുടെ ബാങ്കിൽ നിന്ന് ഉറപ്പാക്കുന്നു…",
      confirmingDetail: "സാധാരണ ഒരു മിനിറ്റിൽ താഴെ മതി. WhatsApp-ലേക്ക് മടങ്ങാം — Premium സ്വയം ഓണാകും.",
      slow: "ബാങ്കിന്റെ ഉറപ്പ് ഇനിയും വന്നിട്ടില്ല. ഉറപ്പായാൽ Premium ഓണാകും; പണം പോയിട്ടും ഉറപ്പായില്ലെങ്കിൽ ബാങ്ക് തിരികെ തരും.",
      failed: "പേയ്മെന്റ് നടന്നില്ല",
      failedDetail: "പണമൊന്നും എടുത്തിട്ടില്ല. അക്കൗണ്ടിൽ നിന്ന് പണം പോയെങ്കിൽ 5–7 പ്രവൃത്തി ദിവസത്തിനകം ബാങ്ക് തിരികെ തരും.",
      retry: "വീണ്ടും ശ്രമിക്കൂ",
    },
  },
};
