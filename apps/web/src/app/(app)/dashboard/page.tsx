"use client";
import { DashboardScreen } from "@/components/money/dashboard-screen";
import { useMoney } from "@/hooks/use-money";
export default function DashboardPage() {
  const { data, error, refresh, simulation, busy, runSimulation } = useMoney();
  return (
    <DashboardScreen
      data={data}
      error={error}
      refresh={refresh}
      simulation={simulation}
      busy={busy}
      onSimulate={(amount) => void runSimulation(amount)}
    />
  );
}
