import type { Metadata } from "next";

export const SITE_URL = "https://finboy.io";
export const SITE_TITLE = "AI Expense Tracker for India | FinBoy";
export const SITE_DESCRIPTION = "Track expenses on WhatsApp or the web with FinBoy. Add voice entries, capture UPI screenshots and import supported Google Pay statements.";
export const SOCIAL_IMAGE = { url: "/opengraph-image", width: 1200, height: 630, alt: "FinBoy — your money, made easier to track" };

export function publicMetadata(path: string, title: string, description: string): Metadata {
  return {
    title,
    description,
    robots: { index: true, follow: true },
    alternates: { canonical: path },
    openGraph: { type: "website", siteName: "FinBoy", locale: "en_IN", url: path, title, description, images: [SOCIAL_IMAGE] },
    twitter: { card: "summary_large_image", title, description, images: [SOCIAL_IMAGE.url] },
  };
}
