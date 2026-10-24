import type { Metadata } from "next";
import { Suspense } from "react";
import { LoadingPanel } from "@/components/feedback/states";
import { TransactionsScreen } from "@/components/records/transactions-screen";

export const metadata: Metadata = { title: "Transactions" };

export default function TransactionsPage() {
  return (
    <Suspense fallback={<LoadingPanel label="Loading records…" />}>
      <TransactionsScreen />
    </Suspense>
  );
}
