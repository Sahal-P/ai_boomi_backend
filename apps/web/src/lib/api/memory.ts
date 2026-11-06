import { z } from "zod";
import { apiFetch, failure, jsonBody, requestJson } from "./http.ts";

// What FinBoy remembers about the household (docs/advisor-round/contract.md).
export const memoryKinds = ["about", "goal", "plan", "preference", "person", "note"] as const;
export type MemoryKind = (typeof memoryKinds)[number];

const memorySchema = z.object({
  id: z.uuid(),
  kind: z.enum(memoryKinds),
  text: z.string().min(1),
  source: z.enum(["web", "whatsapp", "user"]),
  created_at: z.iso.datetime({ offset: true }),
  updated_at: z.iso.datetime({ offset: true }),
});
export type Memory = z.infer<typeof memorySchema>;

const listSchema = z.object({
  enabled: z.boolean(),
  limit: z.number().int().positive(),
  memories: z.array(memorySchema),
  chats: z.number().int().nonnegative(),
});
export type MemoryList = z.infer<typeof listSchema>;

export const MEMORY_TEXT_LIMIT = 300;

export const listMemories = (signal?: AbortSignal) =>
  requestJson("/api/v1/memory", listSchema, { signal });

export const editMemory = (id: string, text: string) =>
  requestJson(`/api/v1/memory/${encodeURIComponent(id)}`, memorySchema, {
    method: "PATCH",
    ...jsonBody({ text }),
  });

export async function deleteMemory(id: string): Promise<void> {
  const response = await apiFetch(`/api/v1/memory/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
  if (!response.ok) throw await failure(response);
}

export const deleteMemories = () =>
  requestJson("/api/v1/memory", z.object({ deleted: z.number().int() }), { method: "DELETE" });

export const setMemoryEnabled = (enabled: boolean) =>
  requestJson("/api/v1/memory/settings", z.object({ enabled: z.boolean() }), {
    method: "PUT",
    ...jsonBody({ enabled }),
  });
