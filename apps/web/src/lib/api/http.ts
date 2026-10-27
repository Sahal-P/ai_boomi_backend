import { z } from "zod";
import { emitSessionEvent } from "../session-events.ts";

/** How a request failed, so each task can explain what happened without internals. */
export type ApiErrorKind =
  | "session"
  | "forbidden"
  | "not_found"
  | "conflict"
  | "validation"
  | "rate_limited"
  | "unavailable"
  | "offline"
  | "network"
  | "timeout"
  | "invalid_response"
  | "configuration";

export class ApiError extends Error {
  readonly status: number | undefined;
  readonly code: string | undefined;
  readonly requestId: string | undefined;
  readonly kind: ApiErrorKind;

  constructor(
    message: string,
    status?: number,
    details: { code?: string | undefined; requestId?: string | undefined; kind?: ApiErrorKind } = {},
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = details.code;
    this.requestId = details.requestId;
    this.kind = details.kind ?? kindForStatus(status);
  }
}

function kindForStatus(status: number | undefined): ApiErrorKind {
  if (status === undefined) return "network";
  if (status === 401) return "session";
  if (status === 403) return "forbidden";
  if (status === 404) return "not_found";
  if (status === 409) return "conflict";
  if (status === 429) return "rate_limited";
  if (status === 400 || status === 413 || status === 422) return "validation";
  if (status >= 500) return "unavailable";
  return "invalid_response";
}

// Only fixed machine codes and generated request IDs are kept; envelope messages are not shown.
const envelopeSchema = z.object({
  error: z.object({
    code: z.string().regex(/^[a-z0-9_.-]{1,64}$/),
    request_id: z
      .string()
      .regex(/^[A-Za-z0-9-]{1,64}$/)
      .optional(),
  }),
});
// Wrong-password and throttled sign-in attempts are not an expired session.
const notExpiry = new Set(["invalid_credentials", "try_later", "invalid_sign_in"]);

export function apiBaseUrl(): string {
  const value = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
  if (value === "/") return "";
  try {
    const url = new URL(value);
    if (
      !["http:", "https:"].includes(url.protocol) ||
      url.username ||
      url.password ||
      url.search ||
      url.hash
    ) {
      throw new Error("Invalid origin");
    }
    return url.toString().replace(/\/$/, "");
  } catch {
    throw new ApiError("The backend URL is not configured correctly.", undefined, {
      kind: "configuration",
    });
  }
}

type RequestInitWithTimeout = Omit<RequestInit, "signal"> & {
  signal?: AbortSignal | null | undefined;
  timeoutMs?: number;
};

type JsonRequestInit<T> = RequestInitWithTimeout & {
  // Health is a readiness contract with a valid, schema-checked 503 response.
  statusSchemas?: Readonly<Record<number, z.ZodType<T>>>;
};

/** Fetches an API path with first-party credentials only, a bounded timeout and classified failures. */
export async function apiFetch(
  path: string,
  init: RequestInitWithTimeout = {},
): Promise<Response> {
  if (!path.startsWith("/") || path.startsWith("//")) {
    throw new ApiError("The backend path is not configured correctly.", undefined, {
      kind: "configuration",
    });
  }
  const { timeoutMs = 5_000, signal, ...requestInit } = init;
  const base = apiBaseUrl();
  const timeout = AbortSignal.timeout(timeoutMs);
  const headers = new Headers(requestInit.headers);
  if (!headers.has("Accept")) headers.set("Accept", "application/json");
  try {
    return await fetch(`${base}${path}`, {
      ...requestInit,
      headers,
      cache: "no-store",
      credentials: base === "" ? "same-origin" : "omit",
      signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
    });
  } catch (reason) {
    // Caller cancellation stays an AbortError so hooks can ignore superseded requests.
    if (signal?.aborted) throw reason;
    if (timeout.aborted) {
      throw new ApiError("FinBoy took too long to respond.", undefined, { kind: "timeout" });
    }
    const offline = typeof navigator !== "undefined" && navigator.onLine === false;
    throw new ApiError("FinBoy could not be reached.", undefined, {
      kind: offline ? "offline" : "network",
    });
  }
}

/** Converts a failed response into an ApiError, signalling an expired household session. */
export async function failure(response: Response): Promise<ApiError> {
  let code: string | undefined;
  let requestId: string | undefined;
  try {
    const parsed = envelopeSchema.safeParse(await response.json());
    if (parsed.success) {
      code = parsed.data.error.code;
      requestId = parsed.data.error.request_id;
    }
  } catch {
    // Non-JSON failures keep only their status.
  }
  if (response.status === 401 && !(code && notExpiry.has(code))) emitSessionEvent("expired");
  return new ApiError("FinBoy could not complete the request.", response.status, {
    code,
    requestId,
  });
}

export async function requestJson<T>(
  path: string,
  schema: z.ZodType<T>,
  init: JsonRequestInit<T> = {},
): Promise<T> {
  const { statusSchemas, ...requestInit } = init;
  const response = await apiFetch(path, requestInit);
  const responseSchema = statusSchemas ? statusSchemas[response.status] : schema;
  if (!responseSchema || (!statusSchemas && !response.ok)) throw await failure(response);
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new ApiError("FinBoy received an unexpected response.", response.status, {
      kind: "invalid_response",
    });
  }
  const result = responseSchema.safeParse(payload);
  if (!result.success) {
    throw new ApiError("FinBoy received an unexpected response.", response.status, {
      kind: "invalid_response",
    });
  }
  return result.data;
}

export function jsonBody(value: unknown): Pick<RequestInit, "body" | "headers"> {
  return { headers: { "Content-Type": "application/json" }, body: JSON.stringify(value) };
}

export function isAbort(reason: unknown): boolean {
  return reason instanceof DOMException && reason.name === "AbortError";
}

/** Builds a query string from defined values only, so URLs never carry empty filters. */
export function query(values: Record<string, string | number | null | undefined>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (value !== null && value !== undefined && value !== "") params.set(key, String(value));
  }
  const text = params.toString();
  return text ? `?${text}` : "";
}
