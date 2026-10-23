"use client";
import { TransactionsScreen } from "@/components/money/transactions-screen";
import { useTransactions } from "@/hooks/use-transactions";
export default function TransactionsPage() {
  const state = useTransactions();
  return (
    <TransactionsScreen
      {...state}
      inspect={(id) => void state.inspect(id)}
      mutate={(...args) => void state.mutate(...args)}
    />
  );
}
