import { chatLink, type SessionView } from "./api/auth.ts";

/**
 * Public pages send signed-in households to the dashboard. For visitors, one tap opens the
 * WhatsApp chat while sign-ups are open, or the sign-in page with the other ways in.
 */
export type WhatsAppEntry =
  | { kind: "loading" }
  | { kind: "dashboard" }
  | { kind: "chat"; href: string }
  | { kind: "web" };

export const WEB_START = "/login";
export const DASHBOARD = "/dashboard";

export function entryFor(
  session: Pick<SessionView, "authenticated" | "sign_in"> | null,
  greeting = "Hi FinBoy",
): WhatsAppEntry {
  if (session?.authenticated) return { kind: "dashboard" };
  const signIn = session?.sign_in;
  if (signIn?.whatsapp && signIn.signup_open && signIn.whatsapp_number) {
    return { kind: "chat", href: chatLink(signIn.whatsapp_number, greeting) };
  }
  return { kind: "web" };
}

/**
 * A page that knows FinBoy's public number when it is built opens the chat from its first paint
 * (docs/ad-journey-round/contract.md); the session check then sends signed-in households to their
 * dashboard and, while sign-ups are closed, everyone else to the sign-in page. If the check can't
 * reach FinBoy, the chat link stays: WhatsApp still delivers the greeting.
 */
export function entryWithNumber(
  session: Pick<SessionView, "authenticated" | "sign_in"> | null | undefined,
  number: string | null,
  greeting = "Hi FinBoy",
): WhatsAppEntry {
  if (session === undefined) return number ? { kind: "chat", href: chatLink(number, greeting) } : { kind: "loading" };
  if (session === null && number) return { kind: "chat", href: chatLink(number, greeting) };
  return entryFor(session, greeting);
}
