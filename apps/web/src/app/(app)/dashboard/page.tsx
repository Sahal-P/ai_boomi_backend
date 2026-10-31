import type { Metadata } from "next";
import { Suspense } from "react";
import { LoadingPanel } from "@/components/feedback/states";
import { OverviewScreen } from "@/components/money/overview-screen";

export const metadata: Metadata = { title: "Home" };

export default function DashboardPage() {
  return (
    <Suspense fallback={<LoadingPanel label="Loading your month…" />}>
      <OverviewScreen />
    </Suspense>
  );
}
