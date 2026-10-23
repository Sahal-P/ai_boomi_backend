"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getSession, signIn, signOut } from "@/lib/api/auth";

export function useHousehold() {
  const [state, setState] = useState<"loading" | "ready" | "error">("loading");
  const [required, setRequired] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const router = useRouter();
  useEffect(() => {
    const controller = new AbortController();
    getSession(controller.signal).then((session) => {
      if (!session.authenticated) router.replace("/login");
      else { setRequired(session.required); setState("ready"); }
    }).catch(() => { if (!controller.signal.aborted) setState("error"); });
    return () => controller.abort();
  }, [router, attempt]);
  return { state, required, retry: () => setAttempt((value) => value + 1), logout: async () => {
    await signOut(); router.replace("/login"); router.refresh();
  } };
}

export function useHouseholdLogin() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const router = useRouter();
  return { busy, error, submit: async (password: string) => {
    setBusy(true); setError("");
    try { await signIn(password); router.replace("/dashboard"); router.refresh(); }
    catch { setError("Unable to sign in. Check your password, or try again in a minute."); }
    finally { setBusy(false); }
  } };
}
