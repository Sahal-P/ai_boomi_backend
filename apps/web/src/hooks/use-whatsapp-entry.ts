"use client";

import { useEffect, useState } from "react";
import { getSession, type SessionView } from "@/lib/api/auth";
import { isAbort } from "@/lib/api/http";
import { entryWithNumber, type WhatsAppEntry } from "@/lib/whatsapp-entry";

type Seen = Pick<SessionView, "authenticated" | "sign_in"> | null | undefined;

/**
 * Shares the session and sign-up result across the public page's actions. `number` is FinBoy's
 * public WhatsApp number when the page was built with it, so its chat link works before the check.
 */
export function useWhatsAppEntry(greeting = "Hi FinBoy", number: string | null = null): WhatsAppEntry {
  const [seen, setSeen] = useState<Seen>(undefined);
  useEffect(() => {
    const controller = new AbortController();
    const refresh = () => {
      void getSession(controller.signal).then(
        (session) => {
          if (!controller.signal.aborted) setSeen(session);
        },
        (error: unknown) => {
          if (controller.signal.aborted || isAbort(error)) return;
          setSeen(null);
        },
      );
    };
    const onPageShow = (event: PageTransitionEvent) => {
      if (event.persisted) refresh();
    };
    refresh();
    window.addEventListener("pageshow", onPageShow);
    return () => {
      controller.abort();
      window.removeEventListener("pageshow", onPageShow);
    };
  }, []);
  return entryWithNumber(seen, number, greeting);
}
