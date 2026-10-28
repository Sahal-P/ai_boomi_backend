import type { HealthResponse } from "./api/health.ts";

/**
 * Asks the API twice before calling it unreachable: one lost request on a phone network is not an
 * outage. Resolves to the health (a degraded answer included) or null when both attempts fail;
 * cancellation rejects.
 */
export async function checkHealth(
  get: (signal: AbortSignal) => Promise<HealthResponse>,
  signal: AbortSignal,
  retryAfterMs = 3_000,
): Promise<HealthResponse | null> {
  for (let attempt = 0; attempt < 2; attempt += 1) {
    if (attempt > 0) await pause(retryAfterMs, signal);
    try {
      return await get(signal);
    } catch (error) {
      if (signal.aborted) throw error;
    }
  }
  return null;
}

function pause(milliseconds: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(resolve, milliseconds);
    signal.addEventListener(
      "abort",
      () => {
        clearTimeout(timer);
        reject(signal.reason);
      },
      { once: true },
    );
  });
}
