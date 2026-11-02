import type { Metadata } from "next";
import { Suspense } from "react";
import { PlanScreen } from "@/components/billing/plan-screen";
import { LoadingPanel } from "@/components/feedback/states";

// PayU checks that payments come from the registered website: share only the origin with it.
export const metadata: Metadata = { title: "Your plan", referrer: "strict-origin" };

export default function PlanPage() {
  return (
    <Suspense fallback={<LoadingPanel label="Loading your plan…" />}>
      <PlanScreen />
    </Suspense>
  );
}
