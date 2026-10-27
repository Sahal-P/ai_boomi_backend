"use client";

import { LoaderCircle } from "lucide-react";
import type { ReactNode } from "react";
import { HouseholdContext } from "@/components/app-shell/household-context";
import { SessionExpiredDialog } from "@/components/app-shell/session-expired";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { useHouseholdSession } from "@/hooks/use-household";

export function HouseholdGate({ children }: { children: ReactNode }) {
  const session = useHouseholdSession();
  if (session.state !== "ready") {
    return (
      <main className="bg-field grid min-h-dvh place-items-center p-6">
        {session.state === "checking" || !session.problem ? (
          <p role="status" className="surface flex items-center gap-3 rounded-3xl p-6 text-sm">
            <LoaderCircle className="size-4 motion-safe:animate-spin" aria-hidden="true" />
            Checking private access…
          </p>
        ) : (
          <div className="w-full max-w-md">
            <ProblemNotice problem={session.problem} onRetry={session.retry} />
            <p className="mt-3 text-center text-xs text-ink-soft">Your records remain private.</p>
          </div>
        )}
      </main>
    );
  }
  return (
    <HouseholdContext
      value={{ required: session.required, household: session.household, signIn: session.signIn }}
    >
      {children}
      <SessionExpiredDialog />
    </HouseholdContext>
  );
}
