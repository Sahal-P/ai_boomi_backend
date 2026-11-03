import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { SITE_URL } from "@/lib/seo/metadata";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(SITE_URL),
  title: { default: "FinBoy — AI Expense Tracker for India", template: "%s · FinBoy" },
  applicationName: "FinBoy",
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  themeColor: "#e1e3e6",
  colorScheme: "light",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en-IN">
      <body>{children}</body>
    </html>
  );
}
