"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { getSession, signIn, signOut } from "@/lib/api/auth";
import { isAbort } from "@/lib/api/http";
import { describeProblem, type Problem } from "@/lib/messages";
import { emitSessionEvent } from "@/lib/session-events";

export type HouseholdState = "checking" | "ready" | "unavailable";

/** Checks private household access once per app visit and sends signed-out visits to sign-in. */
export function useHouseholdSession() {
  const router = useRouter();
  const [state, setState] = useState<HouseholdState>("checking");
  const [required, setRequired] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    getSession(controller.signal).then(
      (session) => {
        if (controller.signal.aborted) return;
        if (!session.authenticated) {
          const here = `${window.location.pathname}${window.location.search}`;
          router.replace(`/login?next=${encodeURIComponent(here)}`);
          return;
        }
        setRequired(session.required);
        setState("ready");
      },
      (error: unknown) => {
        if (controller.signal.aborted || isAbort(error)) return;
        setProblem(describeProblem(error, "FinBoy couldn't check your private access"));
        setState("unavailable");
      },
    );
    return () => controller.abort();
  }, [router, attempt]);
  return {
    state,
    required,
    problem,
    retry: () => {
      setState("checking");
      setAttempt((value) => value + 1);
    },
  };
}

export function useSignOut() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  return {
    busy,
    problem,
    signOut: async () => {
      setBusy(true);
      setProblem(null);
      try {
        await signOut();
        router.replace("/login");
        router.refresh();
      } catch (error) {
        setProblem(describeProblem(error, "You're still signed in"));
      } finally {
        setBusy(false);
      }
    },
  };
}

/** Submits the household password once; it is never stored, logged or kept after submit. */
export function useSignIn(onSuccess: () => void) {
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  return {
    busy,
    problem,
    submit: async (password: string) => {
      setBusy(true);
      setProblem(null);
      try {
        await signIn(password);
        emitSessionEvent("restored");
        onSuccess();
      } catch (error) {
        setProblem(describeProblem(error, "You're not signed in yet"));
      } finally {
        setBusy(false);
      }
    },
  };
}
