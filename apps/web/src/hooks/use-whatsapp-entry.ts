"use client";

import { useEffect, useState } from "react";
import { getSession } from "@/lib/api/auth";
import { isAbort } from "@/lib/api/http";
import { entryFor, type WhatsAppEntry } from "@/lib/whatsapp-entry";

/** Asks the API once whether WhatsApp sign-up is open; any failure leads to the sign-in page. */
export function useWhatsAppEntry(): WhatsAppEntry {
  const [entry, setEntry] = useState<WhatsAppEntry>({ kind: "loading" });
  useEffect(() => {
    const controller = new AbortController();
    getSession(controller.signal).then(
      ({ sign_in }) => {
        if (!controller.signal.aborted) setEntry(entryFor(sign_in));
      },
      (error: unknown) => {
        if (controller.signal.aborted || isAbort(error)) return;
        setEntry(entryFor(null));
      },
    );
    return () => controller.abort();
  }, []);
  return entry;
}
