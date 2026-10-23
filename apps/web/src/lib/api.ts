type HealthService = {
  service: "finboy-api";
  version: string;
};

export type HealthResponse = HealthService &
  (
    | { status: "ok"; database: "connected" }
    | { status: "degraded"; database: "unavailable" }
  );

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

function isHealthResponse(value: unknown): value is HealthResponse {
  if (typeof value !== "object" || value === null) return false;
  if (!("service" in value) || value.service !== "finboy-api") return false;
  if (
    !("version" in value) ||
    typeof value.version !== "string" ||
    !value.version
  )
    return false;
  if (!("status" in value) || !("database" in value)) return false;
  return (
    (value.status === "ok" && value.database === "connected") ||
    (value.status === "degraded" && value.database === "unavailable")
  );
}

export async function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  const timeout = AbortSignal.timeout(5_000);
  const response = await fetch(`${apiBaseUrl()}/api/v1/health`, {
    headers: { Accept: "application/json" },
    cache: "no-store",
    credentials: "omit",
    signal: signal ? AbortSignal.any([signal, timeout]) : timeout,
  });

  if (response.status !== 200 && response.status !== 503) {
    throw new ApiError(
      "FinBoy could not check the connection.",
      response.status,
    );
  }

  let payload: unknown;
  try {
    payload = await response.json();
  } catch {
    throw new ApiError(
      "FinBoy received an unexpected response.",
      response.status,
    );
  }

  if (
    !isHealthResponse(payload) ||
    (response.status === 200 && payload.status !== "ok") ||
    (response.status === 503 && payload.status !== "degraded")
  ) {
    throw new ApiError(
      "FinBoy received an unexpected response.",
      response.status,
    );
  }
  return payload;
}
