import type { Metadata } from "next";
import { Suspense } from "react";
import { LoadingPanel } from "@/components/feedback/states";
import { ReportsScreen } from "@/components/reports/reports-screen";

export const metadata: Metadata = { title: "Reports" };

export default function ReportsPage() {
  return (
    <Suspense fallback={<LoadingPanel label="Loading your reports…" />}>
      <ReportsScreen />
    </Suspense>
  );
}
