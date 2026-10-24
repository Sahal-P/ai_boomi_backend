import { z } from "zod";
import { jsonBody, requestJson } from "./http.ts";

export const getSession = (signal?: AbortSignal) =>
  requestJson(
    "/api/v1/auth/session",
    z.object({ authenticated: z.boolean(), required: z.boolean() }),
    { signal },
  );
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
