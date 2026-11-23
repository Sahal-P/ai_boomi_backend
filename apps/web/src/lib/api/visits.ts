import { apiFetch, jsonBody } from "./http.ts";

/**
 * Where a sign-up came from (docs/ad-journey-round/contract.md). A page with FinBoy's WhatsApp
 * button makes a random ref, records the visit with the link's utm_* tags and adds the ref to the
 * prefilled greeting; FinBoy removes it from the first message and links the new household to the
 * visit. An fbclid is only noted, never sent. Nothing here waits on the network or can block the
 * button.
 */

export type PageLanguage = "en" | "hi" | "ml";

export type Utm = {
  source: string | null;
  medium: string | null;
  campaign: string | null;
  content: string | null;
  meta_click: boolean;
};

// The login-code alphabet: no 0/O or 1/I to misread. 32 letters, so a byte maps evenly.
const ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ";
export const REF_PATTERN = /^[2-9A-HJ-NP-Z]{6}$/;
const TAG = /^[a-z0-9._-]{1,64}$/;
const STORAGE_KEY = "finboy.visit";

const GREETINGS: Record<PageLanguage, string> = {
  en: "Hi FinBoy",
  hi: "नमस्ते FinBoy",
  ml: "നമസ്കാരം FinBoy",
};

export function newRef(fill: (bytes: Uint8Array) => Uint8Array = (bytes) => crypto.getRandomValues(bytes)): string {
  return Array.from(fill(new Uint8Array(6)), (byte) => ALPHABET[byte % ALPHABET.length]).join("");
}

function tag(value: string | null): string | null {
  const cleaned = value?.trim().toLowerCase() ?? "";
  return TAG.test(cleaned) ? cleaned : null;
}

/** The link's campaign tags as FinBoy keeps them; anything else is dropped. */
export function readUtm(search: string): Utm {
  const params = new URLSearchParams(search);
  return {
    source: tag(params.get("utm_source")),
    medium: tag(params.get("utm_medium")),
    campaign: tag(params.get("utm_campaign")),
    content: tag(params.get("utm_content")),
    meta_click: params.has("fbclid"),
  };
}

/** The WhatsApp greeting a page prefills; FinBoy reads it as the greeting alone. */
export function greeting(language: PageLanguage, ref: string | null): string {
  const words = GREETINGS[language];
  return ref && REF_PATTERN.test(ref) ? `${words} (ref ${ref})` : words;
}

/** This tab's visit ref, if it has one (also read by sign-in on /login). */
export function savedRef(): string | null {
  try {
    const value = sessionStorage.getItem(STORAGE_KEY);
    return value && REF_PATTERN.test(value) ? value : null;
  } catch {
    return null;
  }
}

/** This tab's ref, made and kept on first use. Storage may be off (a private tab): then one per load. */
export function visitRef(): string {
  const known = savedRef();
  if (known) return known;
  const ref = newRef();
  try {
    sessionStorage.setItem(STORAGE_KEY, ref);
  } catch {
    // Storage is off; the ref still works for this page.
  }
  return ref;
}

/** Records the visit once per ref; the API ignores a ref it has seen. Never throws. */
export async function recordVisit(visit: { ref: string; landing: string; language: PageLanguage } & Utm): Promise<void> {
  try {
    await apiFetch("/api/v1/visits", { method: "POST", keepalive: true, timeoutMs: 8_000, ...jsonBody(visit) });
  } catch {
    // Tracking never gets in the way of signing up.
  }
}

/** The WhatsApp button was tapped; `keepalive` lets it finish as WhatsApp opens. Never throws. */
export function tapVisit(ref: string | null): void {
  if (!ref || !REF_PATTERN.test(ref)) return;
  void apiFetch("/api/v1/visits/tap", { method: "POST", keepalive: true, ...jsonBody({ ref }) }).catch(() => undefined);
}
