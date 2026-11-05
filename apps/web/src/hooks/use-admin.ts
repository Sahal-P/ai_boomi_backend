"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { adminSignIn, adminSignOut, getAdminSession, type AdminSession } from "@/lib/api/admin";
import { ApiError, isAbort } from "@/lib/api/http";
import { describeProblem, type Problem } from "@/lib/messages";
import { onSessionEvent } from "@/lib/session-events";

export type AdminState = "checking" | "ready" | "unavailable";

/** Sends the browser to admin sign-in, coming back to this page afterwards. */
function useToSignIn() {
  const router = useRouter();
  return useCallback(() => {
    const here = `${window.location.pathname}${window.location.search}`;
    router.replace(`/admin/login?next=${encodeURIComponent(here)}`);
  }, [router]);
}

/**
 * Checks the admin session once per visit. The household session never counts, and a request
 * that finds the admin session gone (expired, revoked, disabled) sends the browser to sign in.
 */
export function useAdminSession() {
  const toSignIn = useToSignIn();
  const [state, setState] = useState<AdminState>("checking");
  const [session, setSession] = useState<AdminSession | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    getAdminSession(controller.signal).then(
      (value) => {
        if (controller.signal.aborted) return;
        setSession(value);
        setState("ready");
      },
      (error: unknown) => {
        if (controller.signal.aborted || isAbort(error)) return;
        if (error instanceof ApiError && error.kind === "session") {
          toSignIn();
          return;
        }
        setProblem(describeProblem(error, "FinBoy couldn't check your admin session"));
        setState("unavailable");
      },
    );
    return () => controller.abort();
  }, [toSignIn, attempt]);
  useEffect(() => onSessionEvent("expired", toSignIn), [toSignIn]);
  const passwordChanged = useCallback(
    () => setSession((current) => (current ? { ...current, must_change_password: false } : current)),
    [],
  );
  return {
    state,
    session,
    problem,
    passwordChanged,
    retry: () => {
      setState("checking");
      setAttempt((value) => value + 1);
    },
  };
}

/** Submits an email and password once; neither is stored, logged or kept after submit. */
export function useAdminSignIn(onSuccess: (session: AdminSession) => void) {
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  return {
    busy,
    problem,
    submit: async (email: string, password: string) => {
      setBusy(true);
      setProblem(null);
      try {
        onSuccess(await adminSignIn(email, password));
      } catch (error) {
        setProblem(describeProblem(error, "You're not signed in"));
      } finally {
        setBusy(false);
      }
    },
  };
}

export function useAdminSignOut() {
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
        await adminSignOut();
        router.replace("/admin/login");
      } catch (error) {
        setProblem(describeProblem(error, "You're still signed in"));
        setBusy(false);
      }
    },
  };
}
