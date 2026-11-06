import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { GlassProvider } from "@/components/liquid-glass/glass-provider";
import { GLASS_LOOK_SCRIPT } from "@/lib/liquid-glass/look";
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
  // Liquid Glass: the saved Clear · Tinted look is applied before first paint (the inline script
  // edits <html>, hence suppressHydrationWarning); GlassProvider picks the rendering tier after.
  return (
    <html lang="en-IN" data-glass-look="clear" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: GLASS_LOOK_SCRIPT }} />
      </head>
      <body>
        <GlassProvider />
        {children}
      </body>
    </html>
  );
}
