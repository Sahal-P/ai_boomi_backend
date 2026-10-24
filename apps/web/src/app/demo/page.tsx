import type { Metadata } from "next";
import { Suspense } from "react";
import { DemoScreen } from "@/components/demo/demo-screen";

export const metadata: Metadata = {
  title: "Sample household",
  description: "A read-only synthetic household showing how FinBoy presents email-derived money records.",
};

export default function DemoPage() {
  return (
    <Suspense>
      <DemoScreen />
    </Suspense>
  );
}
