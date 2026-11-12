import type { Metadata } from "next";
import { Suspense } from "react";
import { DemoScreen } from "@/components/demo/demo-screen";

export const metadata: Metadata = {
  title: "Sample household",
  robots: { index: false, follow: false },
  description: "A read-only, made-up household showing how FinBoy shows a month: what's left, money in and out, bills and records to check.",
};

export default function DemoPage() {
  return (
    <Suspense>
      <DemoScreen />
    </Suspense>
  );
}
