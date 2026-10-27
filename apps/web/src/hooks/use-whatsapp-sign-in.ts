"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  completeWhatsApp,
  startWhatsApp,
  type WhatsAppStart,
  whatsAppStatus,
} from "@/lib/api/auth";
import { isAbort } from "@/lib/api/http";
import { describeProblem, type Problem } from "@/lib/messages";

export type WhatsAppPhase =
  | { step: "off" }
  | { step: "preparing" }
  | { step: "ready"; start: WhatsAppStart; opened: boolean }
  | { step: "finishing" }
  | { step: "declined"; full: boolean }
  | { step: "problem"; problem: Problem };

const POLL_MS = 2_000;

/**
 * "Continue with WhatsApp". A one-time code is prepared as soon as the page opens, so the button
 * is a plain link: one tap opens WhatsApp with the message typed in, and no pop-up blocker gets in
 * the way. This page then waits for the ✅ tap on WhatsApp and finishes here. Expired codes are
 * replaced quietly; the browser never stores a code.
 */
export function useWhatsAppSignIn({
  enabled,
  purpose = "sign_in",
  onDone,
}: {
  enabled: boolean;
  purpose?: "sign_in" | "link";
  onDone: (result: "signed_in" | "linked") => void;
}) {
  const [phase, setPhase] = useState<WhatsAppPhase>({ step: "preparing" });
  const [attempt, setAttempt] = useState(0);
  const done = useRef(onDone);
  useEffect(() => {
    done.current = onDone;
  });

  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    startWhatsApp(purpose, controller.signal).then(
      (start) => {
        if (!controller.signal.aborted) setPhase({ step: "ready", start, opened: false });
      },
      (error: unknown) => {
        if (controller.signal.aborted || isAbort(error)) return;
        setPhase({ step: "problem", problem: describeProblem(error, "WhatsApp sign-in couldn't start") });
      },
    );
    return () => controller.abort();
  }, [enabled, purpose, attempt]);

  const watching = phase.step === "ready";
  useEffect(() => {
    if (!watching) return;
    let stopped = false;
    let checking = false;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const controller = new AbortController();
    const schedule = () => {
      clearTimeout(timer);
      if (!stopped) timer = setTimeout(() => void check(), POLL_MS);
    };
    async function check() {
      if (stopped || checking) return;
      if (document.visibilityState === "hidden") {
        schedule();
        return;
      }
      checking = true;
      try {
        const status = await whatsAppStatus(controller.signal);
        if (stopped) return;
        if (status.state === "confirmed") {
          stopped = true;
          setPhase({ step: "finishing" });
          try {
            const result = await completeWhatsApp();
            done.current("linked" in result ? "linked" : "signed_in");
          } catch (error) {
            setPhase({ step: "problem", problem: describeProblem(error, "You're not signed in yet") });
          }
          return;
        }
        if (status.state === "declined") {
          stopped = true;
          setPhase({ step: "declined", full: purpose === "sign_in" && !status.signup_open });
          return;
        }
        if (status.state === "expired" || status.state === "used") {
          stopped = true;
          setPhase({ step: "preparing" });
          setAttempt((value) => value + 1); // a fresh code, quietly
          return;
        }
      } catch (error) {
        if (isAbort(error)) return;
        // A dropped check is simply tried again; the code stays valid until it expires.
      } finally {
        checking = false;
      }
      schedule();
    }
    // Coming back from WhatsApp shows the result at once instead of waiting for the next check.
    const onReturn = () => {
      if (document.visibilityState === "visible") void check();
    };
    document.addEventListener("visibilitychange", onReturn);
    window.addEventListener("focus", onReturn);
    schedule();
    return () => {
      stopped = true;
      clearTimeout(timer);
      controller.abort();
      document.removeEventListener("visibilitychange", onReturn);
      window.removeEventListener("focus", onReturn);
    };
  }, [watching, purpose]);

  const opened = useCallback(() => {
    setPhase((current) => (current.step === "ready" ? { ...current, opened: true } : current));
  }, []);
  const restart = useCallback(() => {
    setPhase({ step: "preparing" });
    setAttempt((value) => value + 1);
  }, []);
  const off: WhatsAppPhase = { step: "off" };
  return { phase: enabled ? phase : off, opened, restart };
}
