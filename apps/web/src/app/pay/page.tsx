import type { Metadata, Viewport } from "next";
import { Suspense } from "react";
import { PayScreen } from "@/components/billing/pay-screen";

export const metadata: Metadata = {
  title: "FinBoy Premium",
  robots: { index: false, follow: false },
  // PayU checks that payments come from the registered website: share only the origin with it.
  referrer: "strict-origin",
};

// A yellow moment, like sign-in; the phone's browser chrome matches it.
export const viewport: Viewport = { themeColor: "#fed234" };

export default function PayPage() {
  return (
    <Suspense>
      <PayScreen />
    </Suspense>
  );
}
