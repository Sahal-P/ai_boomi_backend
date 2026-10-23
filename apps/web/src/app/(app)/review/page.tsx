"use client";
import { TransactionsScreen } from "@/components/money/transactions-screen";
import { useTransactions } from "@/hooks/use-transactions";
export default function ReviewPage() {
  const state = useTransactions(true);
  return (
    <TransactionsScreen
      {...state}
      reviewOnly
      inspect={(id) => void state.inspect(id)}
      mutate={(...args) => void state.mutate(...args)}
    />
  );
}
