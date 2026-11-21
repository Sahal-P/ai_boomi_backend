"use client";

import { useEffect, useState } from "react";
import { getSession } from "@/lib/api/auth";
import { isAbort } from "@/lib/api/http";
import { entryFor, type WhatsAppEntry } from "@/lib/whatsapp-entry";

/** Shares the session and sign-up result across the public page's actions. */
export function useWhatsAppEntry(): WhatsAppEntry {
  const [entry, setEntry] = useState<WhatsAppEntry>({ kind: "loading" });
  useEffect(() => {
    const controller = new AbortController();
    const refresh = () => {
      void getSession(controller.signal).then(
        (session) => {
          if (!controller.signal.aborted) setEntry(entryFor(session));
        },
        (error: unknown) => {
          if (controller.signal.aborted || isAbort(error)) return;
          setEntry(entryFor(null));
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
  return entry;
}
