import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "FinBoy — A little more clarity",
  description:
    "Meet FinBoy, an AI-powered personal finance copilot thoughtfully built for India. An early preview of a clearer money journey.",
  applicationName: "FinBoy",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en-IN">
      <body>{children}</body>
    </html>
  );
}
