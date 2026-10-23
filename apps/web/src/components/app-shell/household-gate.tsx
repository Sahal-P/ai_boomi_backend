"use client";

import type { ReactNode } from "react";
import { useHousehold } from "@/hooks/use-household";
import { Button } from "@/components/ui/button";

export function HouseholdGate({ children }: { children: ReactNode }) {
  const session = useHousehold();
  if (session.state !== "ready") return <div className="grid min-h-screen place-items-center bg-aurora p-8">
    <div role="status" className="surface rounded-3xl p-8 text-center">
      <p>{session.state === "loading" ? "Checking private access…" : "FinBoy is unavailable. Your records remain private."}</p>
      {session.state === "error" && <Button className="mt-4" onClick={session.retry}>Try again</Button>}
    </div>
  </div>;
  return <>{session.required && <div className="fixed right-4 bottom-20 z-50 lg:bottom-4">
    <Button variant="outline" onClick={() => { void session.logout().catch(session.retry); }}>Sign out</Button>
  </div>}{children}</>;
}
