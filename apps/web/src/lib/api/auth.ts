import { z } from "zod";
import { requestJson } from "./http";

export const getSession = (signal?: AbortSignal) => requestJson(
  "/api/v1/auth/session", z.object({ authenticated: z.boolean(), required: z.boolean() }), { signal },
);
export const signIn = (password: string) => requestJson(
  "/api/v1/auth/login", z.object({ authenticated: z.literal(true) }), {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ password }),
  },
);
export const signOut = () => requestJson(
  "/api/v1/auth/logout", z.object({ authenticated: z.literal(false) }), { method: "POST" },
);
