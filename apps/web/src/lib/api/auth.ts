import { z } from "zod";
import { jsonBody, requestJson } from "./http.ts";

const householdSchema = z.object({
  owner: z.boolean(),
  joined_via: z.enum(["whatsapp", "google"]).nullable(),
  // A masked number ("•••• 4821"), "linked" when only the private allowlist knows it, or null.
  whatsapp: z.string().max(40).nullable(),
  google: z.string().max(80).nullable(),
});

const signInSchema = z.object({
  whatsapp: z.boolean(),
  whatsapp_number: z
    .string()
    .regex(/^[0-9]{7,20}$/)
    .nullable(),
  google_client_id: z
    .string()
    .regex(/^[0-9]{6,32}-[a-z0-9]{8,64}\.apps\.googleusercontent\.com$/)
    .nullable(),
  password: z.boolean(),
  signup_open: z.boolean(),
  gmail: z.boolean(),
});

export const sessionSchema = z.object({
  authenticated: z.boolean(),
  required: z.boolean(),
  household: householdSchema.nullable(),
  sign_in: signInSchema,
});
export type SessionView = z.infer<typeof sessionSchema>;
export type Household = z.infer<typeof householdSchema>;

export const getSession = (signal?: AbortSignal) =>
  requestJson("/api/v1/auth/session", sessionSchema, { signal });
/** The password is sent once to the household API and never stored by the browser app. */
export const signIn = (password: string) =>
  requestJson("/api/v1/auth/login", z.object({ authenticated: z.literal(true) }), {
    method: "POST",
    ...jsonBody({ password }),
  });
export const signOut = () =>
  requestJson("/api/v1/auth/logout", z.object({ authenticated: z.literal(false) }), {
    method: "POST",
  });
export const signOutEverywhere = () =>
  requestJson("/api/v1/auth/logout-everywhere", z.object({ authenticated: z.literal(false) }), {
    method: "POST",
  });

const startedSchema = z.object({
  code: z.string().regex(/^[2-9A-HJ-NP-Z]{4}-[2-9A-HJ-NP-Z]{4}$/),
  link: z
    .string()
    .regex(/^https:\/\/wa\.me\/[0-9]{7,20}\?text=[A-Za-z0-9%._~-]+$/)
    .nullable(),
  expires_at: z.iso.datetime({ offset: true }),
});
export type WhatsAppStart = z.infer<typeof startedSchema>;
export const loginStateSchema = z.enum(["pending", "confirmed", "declined", "used", "expired"]);
export type LoginState = z.infer<typeof loginStateSchema>;

// Both providers set the same HttpOnly login cookie. On a fresh page, parallel starts
// could each create a nonce, leaving Google's signed nonce paired with WhatsApp's cookie.
// Wait for each response to install its cookie before starting the other provider.
let signInStart: Promise<void> = Promise.resolve();
function startWithLoginCookie<T>(start: () => Promise<T>): Promise<T> {
  const result = signInStart.then(start);
  signInStart = result.then(() => undefined, () => undefined);
  return result;
}

/** A one-time code to send from the person's own WhatsApp; bound to this browser by a cookie. */
export const startWhatsApp = (purpose: "sign_in" | "link" = "sign_in", signal?: AbortSignal) =>
  startWithLoginCookie(() => requestJson("/api/v1/auth/whatsapp/start", startedSchema, {
    method: "POST",
    signal,
    ...jsonBody({ purpose }),
  }));
export const whatsAppStatus = (signal?: AbortSignal) =>
  requestJson(
    "/api/v1/auth/whatsapp/status",
    z.object({ state: loginStateSchema, signup_open: z.boolean() }),
    { signal },
  );
export const completeWhatsApp = () =>
  requestJson(
    "/api/v1/auth/whatsapp/complete",
    z.union([z.object({ authenticated: z.literal(true) }), z.object({ linked: z.literal(true) })]),
    { method: "POST" },
  );

/** The nonce Google signs into the ID token, bound to this browser's sign-in cookie. */
export const startGoogle = (signal?: AbortSignal) =>
  startWithLoginCookie(() => requestJson(
    "/api/v1/auth/google/start",
    z.object({ nonce: z.string().regex(/^[a-f0-9]{64}$/) }),
    { method: "POST", signal },
  ));
/** The ID token goes once to the backend, which verifies it; the browser keeps nothing. */
export const signInWithGoogle = (credential: string, link = false) =>
  requestJson(
    "/api/v1/auth/google",
    z.union([z.object({ authenticated: z.literal(true) }), z.object({ linked: z.literal(true) })]),
    { method: "POST", ...jsonBody({ credential, link }) },
  );

export const deleteAccount = () =>
  requestJson("/api/v1/account/delete", z.object({ deleted: z.literal(true) }), {
    method: "POST",
    ...jsonBody({ confirm: "DELETE" }),
  });

/** A wa.me link that opens FinBoy's WhatsApp chat with a greeting typed in. */
export function chatLink(number: string, greeting = "Hi FinBoy"): string {
  return `https://wa.me/${number}?text=${encodeURIComponent(greeting)}`;
}

const APP_PATHS = [
  "/dashboard",
  "/transactions",
  "/review",
  "/assistant",
  "/sources",
  "/connect",
  "/import/",
  "/privacy",
];

/**
 * Accepts only a same-origin app path (with its query) as a post-sign-in destination.
 * Anything else — other origins, protocol-relative or encoded tricks — falls back to Overview.
 */
export function safeReturnPath(value: string | null | undefined): string {
  const fallback = "/dashboard";
  if (!value || value.length > 512 || !value.startsWith("/") || /^\/[\\/]/.test(value)) {
    return fallback;
  }
  try {
    const base = "https://finboy.invalid";
    const url = new URL(value, base);
    if (url.origin !== base || url.username || url.password) return fallback;
    const allowed = APP_PATHS.some((path) =>
      path.endsWith("/") ? url.pathname.startsWith(path) : url.pathname === path,
    );
    return allowed ? `${url.pathname}${url.search}` : fallback;
  } catch {
    return fallback;
  }
}
