import type { Metadata } from "next";
import { Suspense } from "react";
import { LoadingPanel } from "@/components/feedback/states";
import { OverviewScreen } from "@/components/money/overview-screen";

export const metadata: Metadata = { title: "Overview" };

export default function DashboardPage() {
  return (
    <Suspense fallback={<LoadingPanel label="Loading your overview…" />}>
      <OverviewScreen />
    </Suspense>
  );
}
