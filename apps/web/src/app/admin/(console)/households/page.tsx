import type { Metadata } from "next";
import { Suspense } from "react";
import { HouseholdsScreen } from "@/components/admin/households-screen";
import { LoadingPanel } from "@/components/feedback/states";

export const metadata: Metadata = { title: "Households" };

export default function AdminHouseholdsPage() {
  return (
    <Suspense fallback={<LoadingPanel label="Loading households…" />}>
      <HouseholdsScreen />
    </Suspense>
  );
}
