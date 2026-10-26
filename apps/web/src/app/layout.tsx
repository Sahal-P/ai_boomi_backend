import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "FinBoy — Your inbox already knows your money",
    template: "%s · FinBoy",
  },
  description:
    "FinBoy turns bank alerts, receipts and bills into a verified money timeline, then answers your questions in Hindi, English, Malayalam or romanized input.",
  applicationName: "FinBoy",
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
