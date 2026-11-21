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

export function entryFor(session: Pick<SessionView, "authenticated" | "sign_in"> | null): WhatsAppEntry {
  if (session?.authenticated) return { kind: "dashboard" };
  const signIn = session?.sign_in;
  if (signIn?.whatsapp && signIn.signup_open && signIn.whatsapp_number) {
    return { kind: "chat", href: chatLink(signIn.whatsapp_number) };
  }
  return { kind: "web" };
}
