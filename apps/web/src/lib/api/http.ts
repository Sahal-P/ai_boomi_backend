import { z } from "zod";

export class ApiError extends Error {
  readonly status: number | undefined;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function apiBaseUrl(): string {
  const value = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";
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
    throw new ApiError("The backend URL is not configured correctly.");
  }
}

type JsonRequestInit<T> = Omit<RequestInit, "signal"> & {
  signal?: AbortSignal | null | undefined;
  timeoutMs?: number;
  // Health is a readiness contract with a valid, schema-checked 503 response.
  statusSchemas?: Readonly<Record<number, z.ZodType<T>>>;
};

export async function requestJson<T>(
  path: string,
  schema: z.ZodType<T>,
  init: JsonRequestInit<T> = {},
): Promise<T> {
  if (!path.startsWith("/") || path.startsWith("//")) {
    throw new ApiError("The backend path is not configured correctly.");
  }
  const { timeoutMs = 5_000, statusSchemas, ...requestInit } = init;
  const timeout = AbortSignal.timeout(timeoutMs);
  const headers = new Headers(init.headers);
  if (!headers.has("Accept")) headers.set("Accept", "application/json");
  const response = await fetch(`${apiBaseUrl()}${path}`, {
    ...requestInit,
    headers,
    cache: "no-store",
    credentials: "omit",
    signal: init.signal ? AbortSignal.any([init.signal, timeout]) : timeout,
  });
  const responseSchema = statusSchemas ? statusSchemas[response.status] : schema;
  if (!responseSchema || (!statusSchemas && !response.ok)) {
    throw new ApiError("FinBoy could not complete the request.", response.status);
  }
  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new ApiError("FinBoy received an unexpected response.", response.status);
  }
  const result = responseSchema.safeParse(payload);
  if (!result.success) {
    throw new ApiError("FinBoy received an unexpected response.", response.status);
  }
  return result.data;
}
