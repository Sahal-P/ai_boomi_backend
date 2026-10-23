import { z } from "zod";
import { requestJson } from "./http.ts";

const service = z.object({
  service: z.literal("finboy-api"),
  version: z.string().min(1),
});
const healthy = service.extend({
  status: z.literal("ok"),
  database: z.literal("connected"),
});
const degraded = service.extend({
  status: z.literal("degraded"),
  database: z.literal("unavailable"),
});
export const healthSchema = z.discriminatedUnion("status", [healthy, degraded]);
export type HealthResponse = z.infer<typeof healthSchema>;

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return requestJson("/api/v1/health", healthSchema, {
    signal,
    statusSchemas: { 200: healthy, 503: degraded },
  });
}
