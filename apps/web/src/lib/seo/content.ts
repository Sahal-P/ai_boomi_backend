export const CONTENT_UPDATED_AT = "2026-11-04";
export type Section = {
  heading: string;
  paragraphs: readonly string[];
  steps?: readonly string[];
  links?: readonly { href: string; label: string }[];
};
export type Content = {
  title: string;
  description: string;
  intro: string;
  updatedAt?: string;
  sections: readonly Section[];
  related: readonly { href: string; label: string }[];
  source?: { href: string; label: string };
};

export const features: Readonly<Record<string, Content>> = {
  "whatsapp-expense-tracker": {
    title: "WhatsApp expense tracker for India",
    description: "Track cash and UPI expenses on WhatsApp with FinBoy. Send a message, correct entries and review your spending in India. Free to start.",
    intro: "Keep an expense diary in a chat you already use. Send FinBoy what you spent on WhatsApp, check its reply, and review your records and budgets on the web. Text entries and typed questions are free; voice, photos and statement import are Premium.",
    updatedAt: "2026-11-15",
    sections: [
      { heading: "From your first message to a spending summary", paragraphs: ["Tap Start on WhatsApp and send the prepared greeting. FinBoy explains what it records and asks for your agreement before you begin. If sign-up is at capacity, follow the available options shown on the sign-in page.", "Try a short note such as ‘chai 20, auto 50, lunch 120’. In this made-up example, FinBoy can save three entries totalling ₹190 and suggest a category for each. Later, send ‘today’, ‘this week’ or ‘this month’ to see recorded spending."], links: [{ href: "/guides/track-expenses-on-whatsapp", label: "Read the daily WhatsApp expense diary guide" }] },
      { heading: "Check the reply and correct mistakes", paragraphs: ["FinBoy saves clear entries and asks for clarification when it is unsure. Check the amount and category in the reply. Tap Amount or Category to fix an entry, or Undo if it should not have been saved.", "For a possible duplicate, a matching screenshot or bill, or an entry of ₹50,000 or more, FinBoy asks before counting it. A screenshot or voice note can still be misread; check the original payment app for payment status."] },
      { heading: "Keep cash and UPI purchases together", paragraphs: ["Add the purchases you want to track by text. With Premium, you can also send a bill photo or UPI payment screenshot, or import a supported Google Pay PDF statement. FinBoy does not automatically see every bank or UPI transaction.", "Review overlaps before relying on a total: a typed entry and a screenshot or statement can describe the same purchase. Your reports reflect the records you add or import, not your live bank balance."], links: [{ href: "/features/upi-expense-tracker", label: "How to record UPI expenses" }, { href: "/guides/track-cash-and-upi-expenses", label: "A practical cash and UPI diary" }] },
      { heading: "Ask about your spending", paragraphs: ["You can type a question about your recorded spending and view Transactions and Reports on the web. Typed questions are free, subject to daily usage limits. The answer is based on the records available to FinBoy, so add or check missing purchases before relying on a total.", "Voice notes and spoken replies in English, Hindi and Malayalam are Premium features. You can continue to use text when speaking is inconvenient."], links: [{ href: "/features/voice-expense-tracker", label: "How voice expense tracking works" }] },
      { heading: "Privacy and plans", paragraphs: ["FinBoy does not need a bank login or access to your SMS. It keeps the structured records you save; diary messages, voice notes and photos are not kept as files. Questions to Ask FinBoy and its replies are saved as chats, and you can delete them.", "Free includes typed entries, typed questions and reports. New households start with 30 days of Premium; after that, Premium is ₹299 a month if you choose it. Gmail import is invite-only and is not required to sign up."], links: [{ href: "/privacy-policy", label: "Read what FinBoy keeps and how to delete it" }, { href: "/pricing", label: "See plans and current terms" }] },
    ],
    related: [{ href: "/guides/track-expenses-on-whatsapp", label: "Follow the WhatsApp expense diary guide" }, { href: "/features/voice-expense-tracker", label: "Record spending by voice" }, { href: "/features/google-pay-statement-import", label: "Import a Google Pay statement" }],
  },
  "voice-expense-tracker": {
    title: "Voice expense tracker for India",
    description: "Record expenses by voice in English, Hindi or Malayalam with FinBoy on WhatsApp or the web. Review amounts and correct mistakes.",
    intro: "Say what you spent and let FinBoy turn the note into an expense entry. Voice entry is useful when typing a full description would interrupt your day. It works alongside text entries, screenshots and supported statements.",
    sections: [
      { heading: "Speak in a supported language", paragraphs: ["FinBoy supports English, Hindi and Malayalam. You can use WhatsApp voice notes or the web app’s voice entry controls. Choose the language and entry option offered by your account.", "For a synthetic example, say ‘spent one hundred and fifty rupees on lunch’. A Hindi example is ‘चाय पर बीस रुपये खर्च किए’. Keep the amount and what you paid for clear. You can type the entry when speaking is inconvenient."] },
      { heading: "Record, then check the result", paragraphs: ["Open your own FinBoy WhatsApp chat and record a normal voice note. On the web, use the quick-add voice controls and allow microphone access if your browser asks.", "Read the resulting entry. Speech recognition can mishear an amount, a name or a category, especially with background noise. Use the correction controls shown in that flow. In the WhatsApp diary, Undo can remove a mistaken saved entry."] },
      { heading: "Use voice and text together", paragraphs: ["A quiet place can make voice recording easier. In a public space, typing may be more comfortable. Neither method requires you to use a special accounting vocabulary.", "Your voice entries join the same recorded history and reports as other entries. Check those records against your own receipts and bank history when reviewing the month."] },
      { heading: "Availability and processing", paragraphs: ["Voice needs an internet connection and an available speech service. It is not an offline transcription tool. If voice is unavailable, the app offers other ways to add an entry.", "Voice is a Premium feature under FinBoy’s published plans. See Pricing for current terms. FinBoy processes audio to read the entry; the Privacy Policy explains the providers and retention rules. This is not an on-device-only service."] },
    ],
    related: [{ href: "/features/whatsapp-expense-tracker", label: "Use the WhatsApp expense diary" }, { href: "/guides/track-expenses-on-whatsapp", label: "Check and correct diary entries" }],
  },
  "upi-expense-tracker": {
    title: "UPI expense tracker for everyday spending",
    description: "Organize UPI expenses with FinBoy using payment screenshots, text or voice. Keep cash purchases alongside them and review your recorded spending.",
    intro: "Small UPI purchases are easy to lose track of. Send a payment screenshot to FinBoy’s WhatsApp diary, or describe the expense in text or voice, to bring it into your recorded spending history.",
    sections: [
      { heading: "Capture a payment you want to record", paragraphs: ["Open the payment details in your UPI app and share a clear screenshot with FinBoy on WhatsApp. Keep the amount, date and relevant payment details legible. A bill photo is another supported way to capture an expense.", "For a synthetic example, a ₹120 lunch payment can become an expense entry with an amount and a suggested category. Use a simple typed entry if a screenshot is unclear or you would prefer to share fewer details."] },
      { heading: "Review the amount and category", paragraphs: ["Check FinBoy’s reply before relying on the entry. Clear diary items are saved, while uncertain details may need clarification. Correct the amount or category using the controls shown, or use Undo for a mistaken entry.", "A screenshot is a record you submit, not independent confirmation that money reached the recipient. Check the original payment app or bank records for payment status."] },
      { heading: "Keep cash and UPI in the same diary", paragraphs: ["Record cash purchases by text or voice and UPI purchases with whichever input is convenient. Consistent categories make the combined spending history easier to review.", "Avoid submitting a typed entry and a screenshot for the same purchase without checking for a duplicate. When importing a statement for a period you have already recorded, review overlapping records before using the totals."] },
      { heading: "Understand the coverage", paragraphs: ["FinBoy works from entries, images and supported imports you provide. It does not automatically read every UPI payment or ask for your net banking password. A missing purchase stays outside your report until recorded.", "Image reading is a Premium feature under the published plans. See Pricing for availability and the Privacy Policy for image processing details. Images are processed by backend providers; capture is not an on-device-only feature."] },
    ],
    related: [{ href: "/guides/track-cash-and-upi-expenses", label: "Track cash and UPI together" }, { href: "/features/google-pay-statement-import", label: "Import a Google Pay statement" }],
  },
  "google-pay-statement-import": {
    title: "Google Pay statement import and expense tracking",
    description: "Import a supported Google Pay PDF statement into FinBoy on the web or WhatsApp. Validate totals and review your transaction history and spending reports.",
    intro: "Bring a period of Google Pay transaction history into FinBoy using a supported PDF statement. The import checks the statement’s own totals before saving records, then makes the recorded transactions available for review and reports.",
    sections: [
      { heading: "Download the statement you need", paragraphs: ["In Google Pay, open See transaction history, then the menu and Get Statement. Select the period, continue, and save or share the PDF. App labels and availability can change; Google’s own help page explains the current steps.", "A Google Pay statement covers the transactions in that service and period. It is not a complete statement of every payment across your bank accounts or other UPI apps."] },
      { heading: "Import on the web or WhatsApp", paragraphs: ["On the web, sign in to FinBoy and open Sources from the account menu. Use Import a Google Pay statement and select the supported PDF. On WhatsApp, send the statement as a document to your own FinBoy diary.", "FinBoy must read every transaction row and reconcile the statement totals before the import saves records. A statement that fails those checks is not partly saved as a successful import."] },
      { heading: "If the import cannot complete", paragraphs: ["Check that you selected the original supported Google Pay PDF and the intended period. Read the explanation shown by FinBoy. An unsupported layout or a statement that cannot be reconciled needs attention before its figures can be trusted.", "This feature does not promise support for arbitrary bank PDFs, credit-card statements or PhonePe statements. You can still add individual expenses by text, voice or screenshot using the available entry options."] },
      { heading: "Review the imported records", paragraphs: ["Check the period and transaction list after a successful import, then explore spending categories and payees in Reports. If you already recorded purchases from the same period, inspect any overlap before relying on the combined totals.", "Statement import is a Premium feature under the published plans. The PDF itself is processed without storing the document; the resulting structured records are retained for your account. See the Privacy Policy for processing and deletion details."] },
    ],
    source: { href: "https://support.google.com/pay/india/answer/7430307?hl=en", label: "Google Pay Help: view transaction history and download statements" },
    related: [{ href: "/guides/download-google-pay-statement", label: "Follow the statement download guide" }, { href: "/features/upi-expense-tracker", label: "Capture individual UPI expenses" }],
  },
};

export const guides: Readonly<Record<string, Content>> = {
  "download-google-pay-statement": {
    title: "How to download a Google Pay transaction statement",
    description: "Learn how to download a Google Pay transaction statement as a PDF, choose a period and check what it covers before importing it.",
    intro: "You can download a PDF of your Google Pay transaction history from the app. Choose the period you need, save the file and check its coverage before using it to review your spending.",
    updatedAt: "2026-11-15",
    sections: [
      { heading: "Download the PDF from Google Pay", paragraphs: ["Google’s help page describes the following steps. Menu labels can change, so check Google’s current instructions if yours look different."], steps: ["Open Google Pay and scroll to See transaction history.", "Tap See transaction history.", "At the top right of the search bar, tap More and then Get Statement.", "Select the statement period.", "Tap Continue to view and save it, or Share to send the PDF."] },
      { heading: "Choose a period that answers your question", paragraphs: ["For a monthly review, select the month you want rather than assuming the default dates cover it. If you only want to check a recent payment in the app, Google Pay also offers date filters for this month, the last 30 days and the last 90 days.", "For example, to review October groceries, choose a statement covering October and look for grocery transactions in that period. This is a made-up example: a shop’s name alone may not tell you what was purchased."] },
      { heading: "Is this a bank statement?", paragraphs: ["No. Google Pay’s transaction history covers activity through Google Pay, not every transaction from your bank account. Cash purchases and payments made through other UPI apps may be missing. Request a bank statement from your bank when you need its complete account record.", "Your statement may contain personal financial details. Save or share it only where you are comfortable doing so; never post a real statement, UPI PIN or OTP in a public forum."], links: [{ href: "/guides/track-cash-and-upi-expenses", label: "How to track cash and UPI expenses together" }] },
      { heading: "If you cannot find a transaction", paragraphs: ["Check that the statement period includes the date you need and that you are looking at the right Google Pay account. Google’s help page also suggests updating the app and checking the email address registered to Google Pay when history is missing.", "If a payment was made through another UPI app or outside Google Pay, look in that app or your bank’s records instead. A missing row does not by itself prove that a payment failed."], links: [{ href: "https://support.google.com/pay/india/answer/7430307?hl=en", label: "Google Pay Help: fix problems viewing transaction history" }] },
      { heading: "Import a supported PDF into FinBoy", paragraphs: ["Statement import is a Premium feature. Sign in to FinBoy, open Sources from the account menu and choose Import a Google Pay statement. You can also send the PDF as a document to your FinBoy WhatsApp chat.", "FinBoy checks every row against the statement’s totals before saving the import. If the file cannot be read or reconciled, check that it is the original supported Google Pay PDF and the intended period; a screenshot or another bank’s PDF is a different input."], links: [{ href: "/features/google-pay-statement-import", label: "How FinBoy imports Google Pay statements" }, { href: "/pricing", label: "See Free and Premium plans" }] },
      { heading: "Review the imported entries", paragraphs: ["After a successful import, check the transaction list and reporting period. If you recorded a purchase manually before importing the same period, inspect the overlap so you do not count it twice.", "The original PDF is processed for the import and is not kept as a document; structured records are kept in your account. Your FinBoy history is not a live bank balance or proof that a payment settled."], links: [{ href: "/privacy-policy", label: "Read FinBoy’s privacy policy" }] },
    ],
    source: { href: "https://support.google.com/pay/india/answer/7430307?hl=en", label: "Google Pay Help: official statement download instructions" },
    related: [{ href: "/features/google-pay-statement-import", label: "How FinBoy statement import works" }, { href: "/guides/track-cash-and-upi-expenses", label: "Include cash and other UPI purchases" }],
  },
  "track-expenses-on-whatsapp": {
    title: "How to track daily expenses on WhatsApp",
    description: "Start a WhatsApp expense diary with FinBoy, record purchases by text or voice, correct mistakes and review your spending.",
    intro: "An expense diary works best when it fits your day. With FinBoy, you can record a purchase in a WhatsApp message and review it later on the web. Start with one clear entry and build the habit from there.",
    sections: [
      { heading: "Set up your own diary", paragraphs: ["Open FinBoy’s sign-in page and follow the current WhatsApp getting-started instructions. Keep the diary tied to your own account. The sign-in page shows signup availability and the login options you can use.", "Before adding real entries, read the Privacy Policy and current plan details. Text, voice and image capture have different availability under the published plans."] },
      { heading: "Record one purchase", paragraphs: ["Use a short description with an amount. Synthetic examples include ‘lunch 150’ and ‘bus 40’. For money received, make that direction clear rather than relying on a bare number.", "You can send a voice note in a supported language or a clear payment screenshot when that is more convenient. FinBoy reads the entry and replies with the result. Speak or type clearly enough that you can recognize what was recorded."] },
      { heading: "Fix mistakes when you see them", paragraphs: ["Check the reply for the amount and category. Use Amount or Category to correct an available diary entry, or Undo if you saved the wrong item. When FinBoy asks for clarification, answer the question rather than repeatedly resending the purchase.", "Avoid sending both a screenshot and a typed entry for the same purchase without checking the history. Repeated submissions can make your own review harder even when you remember only one payment."] },
      { heading: "Review a little at a time", paragraphs: ["Ask for today, this week or this month to review recorded spending. On the web, use Transactions to inspect entries and Reports to see patterns by category and payee.", "Choose a regular review time and compare your entries with your receipts and payment history. Record anything you missed. The diary only covers the information you have added or imported, so its figures may differ from your actual bank balance."] },
    ],
    related: [{ href: "/features/whatsapp-expense-tracker", label: "Explore the WhatsApp expense tracker" }, { href: "/features/voice-expense-tracker", label: "Record an expense by voice" }],
  },
  "track-cash-and-upi-expenses": {
    title: "How to track cash and UPI expenses together",
    description: "Keep cash and UPI purchases in one expense diary, use consistent categories and review entries for gaps and duplicates.",
    intro: "A payment app shows only part of everyday spending. A cash snack, a UPI cab payment and a grocery bill can all belong in the same monthly budget. A combined diary helps you review the purchases together without assuming one payment history is complete.",
    sections: [
      { heading: "Record cash before the details fade", paragraphs: ["Add a cash purchase by text or voice when it is convenient and safe. A synthetic entry such as ‘cash tea 20’ preserves what the money was for. Keep enough description to recognize it during your review.", "Try to use a consistent habit, such as checking for missing purchases at the end of the day. It is easier to remember a small cash expense that evening than several weeks later."] },
      { heading: "Add the UPI purchases you want to track", paragraphs: ["Enter a UPI purchase by text, voice or a payment screenshot in the WhatsApp diary. A supported Google Pay statement can add transaction history for a period.", "FinBoy works from the information you provide. It does not passively see every payment across your UPI apps or bank accounts. Use the original payment app and bank records to check payment status."] },
      { heading: "Use categories consistently", paragraphs: ["Choose categories by what you bought rather than changing them every time you use a different payment method. A synthetic ₹20 cash tea and ₹120 UPI lunch can both contribute to the same food category when that matches your classification.", "Review the suggested category after capture and correct it if needed. This guide describes organizing purchases together; it does not promise a separate automatic cash-versus-UPI chart."] },
      { heading: "Check for missing entries and overlap", paragraphs: ["Compare the diary with receipts and payment history at a regular interval. Add a forgotten cash purchase and inspect possible duplicates, especially when a statement overlaps with previously entered transactions.", "If a monthly total looks surprising, open its contributing records before changing your budget. The useful question is whether the records accurately represent your purchases, rather than whether a partial diary matches a live bank balance."] },
    ],
    related: [{ href: "/features/upi-expense-tracker", label: "Capture UPI expenses" }, { href: "/guides/monthly-household-budget-india", label: "Build a monthly household budget" }],
  },
  "monthly-household-budget-india": {
    title: "How to build a monthly household budget in India",
    description: "Plan a household budget using take-home income, regular commitments and flexible spending, then review it against recorded expenses.",
    intro: "Start a household budget with the money available for the month and the commitments it needs to cover. A useful plan reflects your circumstances and can change when income, bills or essential costs change.",
    sections: [
      { heading: "Begin with take-home income", paragraphs: ["List the income you expect to receive during the month. Separate reliable income from uncertain amounts so you can see which spending depends on money that has not arrived.", "Use take-home figures when planning the money available to spend. Avoid counting an internal transfer between your own accounts as new household income."] },
      { heading: "List commitments before flexible spending", paragraphs: ["Write down known commitments such as rent, utilities, school costs and loan payments. Check their dates so a payment due early in the month is not overlooked.", "Then plan flexible categories such as groceries, transport and meals. Leave room for irregular costs rather than assuming every month will look identical. There is no single category split that fits every household."] },
      { heading: "Work through a simple example", paragraphs: ["Synthetic example: a household planning around ₹40,000 of take-home income reserves ₹22,000 for known commitments and ₹12,000 for flexible spending. That leaves ₹6,000 in the plan for other priorities or unexpected costs.", "Those figures are an illustration, not a recommendation for your household. Check for missing obligations and costs before treating a planned remainder as available money. A budget remainder is not a verified bank balance."] },
      { heading: "Review the plan against your records", paragraphs: ["Use FinBoy’s recorded spending and category budgets to see where actual purchases differ from your plan. Check contributing entries when a category rises, and correct missing or duplicated records before drawing conclusions.", "Review weekly and adjust the next month’s plan using what you learned. FinBoy helps with budgeting and spending discipline; it does not choose investments or guarantee what you can afford. Keep the plan grounded in your own complete financial records."] },
    ],
    related: [{ href: "/guides/track-cash-and-upi-expenses", label: "Keep a more complete expense diary" }, { href: "/features/whatsapp-expense-tracker", label: "Add entries through WhatsApp" }],
  },
};

export function findContent(items: Readonly<Record<string, Content>>, slug: string): Content | undefined {
  return Object.hasOwn(items, slug) ? items[slug] : undefined;
}
