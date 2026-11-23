import type { Metadata, Viewport } from "next";

import { MlLanding } from "@/components/marketing/ml-landing";
import { publicMetadata, SOCIAL_IMAGE } from "@/lib/seo/metadata";

const title = "കണക്കുപുസ്തകം, ഇനി WhatsApp-ൽ";
const description =
  "ചെലവുകൾ WhatsApp-ൽ മെസേജ് പോലെ അയച്ചാൽ മതി. FinBoy ഉടനെ ചേർത്ത് വിഭാഗം തിരിക്കും. മലയാളത്തിൽ എഴുതാം, പറയാം.";
const base = publicMetadata("/ml", title, description);

export const metadata: Metadata = {
  ...base,
  alternates: { canonical: "/ml", languages: { "en-IN": "/", "ml-IN": "/ml" } },
  openGraph: { type: "website", siteName: "FinBoy", locale: "ml_IN", url: "/ml", title, description, images: [SOCIAL_IMAGE] },
};
export const viewport: Viewport = { themeColor: "#fed234" };

// FinBoy's public WhatsApp number, read when the page is built, so the button opens the chat from
// the first paint (docs/ad-journey-round/contract.md). Without it the page asks the API first.
const NUMBER = /^[0-9]{7,20}$/;

export default function MalayalamPage() {
  const number = process.env.FINBOY_WHATSAPP_NUMBER ?? "";
  return <MlLanding number={NUMBER.test(number) ? number : null} />;
}
