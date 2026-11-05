import type { Metadata } from "next";
import { Suspense } from "react";
import { PaymentsScreen } from "@/components/admin/payments-screen";
import { LoadingPanel } from "@/components/feedback/states";

export const metadata: Metadata = { title: "Payments" };

export default function AdminPaymentsPage() {
  return (
    <Suspense fallback={<LoadingPanel label="Loading payments…" />}>
      <PaymentsScreen />
    </Suspense>
  );
}
