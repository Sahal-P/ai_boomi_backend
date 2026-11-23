import type { Metadata } from "next";
import { Suspense } from "react";
import { GrowthScreen } from "@/components/admin/growth-screen";
import { LoadingPanel } from "@/components/feedback/states";

export const metadata: Metadata = { title: "Growth" };

export default function AdminGrowthPage() {
  return (
    <Suspense fallback={<LoadingPanel label="Loading growth…" />}>
      <GrowthScreen />
    </Suspense>
  );
}
