import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import "./globals.css";

export const metadata: Metadata = {
  title: "FinBoy — Your inbox already knows your money",
  description:
    "FinBoy turns bank alerts, receipts and bills into a verified money timeline, then answers your questions in Malayalam, Manglish or English.",
  applicationName: "FinBoy",
};

export const viewport: Viewport = {
  themeColor: "#f5f4fb",
  colorScheme: "light",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en-IN">
      <body>{children}</body>
    </html>
  );
}
