"use client";

import { useEffect, useSyncExternalStore } from "react";
import { readUtm, recordVisit, visitRef, type PageLanguage } from "@/lib/api/visits";

// One ref per page load (and per tab while sessionStorage works), so every render sees the same.
let loaded: string | null = null;
const current = () => (loaded ??= visitRef());
const none = () => null;
const unchanging = () => () => {};

/**
 * This tab's visit ref for the page's WhatsApp link (docs/ad-journey-round/contract.md). The
 * server and hydration render without it, so the first paint's link has no ref; the visit is then
 * recorded in the background and never delays the button.
 */
export function useVisit(language: PageLanguage): string | null {
  const ref = useSyncExternalStore(unchanging, current, none);
  useEffect(() => {
    if (ref) void recordVisit({ ref, landing: window.location.pathname, language, ...readUtm(window.location.search) });
  }, [ref, language]);
  return ref;
}
