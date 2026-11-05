import { chatLink, type SessionView } from "./api/auth.ts";

/**
 * How a visitor starts FinBoy from a public page (docs/signup-round/contract.md). While sign-ups
 * are open, one tap opens FinBoy's WhatsApp chat with "Hi FinBoy" typed in. Otherwise — sign-ups
 * closed, WhatsApp off, or the API unreachable — the sign-in page, which lists every way in and
 * explains a full waitlist.
 */
export type WhatsAppEntry = { kind: "loading" } | { kind: "chat"; href: string } | { kind: "web" };

export const WEB_START = "/login";

export function entryFor(signIn: SessionView["sign_in"] | null): WhatsAppEntry {
  if (signIn?.whatsapp && signIn.signup_open && signIn.whatsapp_number) {
    return { kind: "chat", href: chatLink(signIn.whatsapp_number) };
  }
  return { kind: "web" };
}
