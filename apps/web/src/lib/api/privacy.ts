import { z } from "zod";
import { ApiError, apiFetch, failure, jsonBody, requestJson } from "./http.ts";
import { opaque } from "./money.ts";

const count = z.number().int().nonnegative();
const timestamp = z.iso.datetime({ offset: true });

const auditSchema = z.object({
  id: z.uuid(),
  event_type: z.string().max(80),
  subject_type: z.string().max(80),
  subject_id: z.uuid(),
  created_at: timestamp,
});
export type AuditEvent = z.infer<typeof auditSchema>;

export const deletionPreviewSchema = z.object({
  version: opaque,
  connection_id: z.uuid().nullable(),
  source_count: count,
  event_count: count,
  removed_transaction_count: count,
  retained_shared_transaction_count: count,
  removed_obligation_count: count,
  retained_shared_obligation_count: count,
  first_received_at: timestamp.nullable(),
  last_received_at: timestamp.nullable(),
  backup_retention_days: z.literal(7),
});
export type DeletionPreview = z.infer<typeof deletionPreviewSchema>;

const isolationSchema = z.object({
  data_version: opaque,
  demo_only_transactions: count,
  mixed_transactions: count,
  demo_only_obligations: count,
  quarantined_obligations: count,
});
export type IsolationInventory = z.infer<typeof isolationSchema>;

export const getAuditEvents = (signal?: AbortSignal) =>
  requestJson("/api/v1/privacy/audit-events", z.array(auditSchema), { signal });
export const getIsolation = (signal?: AbortSignal) =>
  requestJson("/api/v1/privacy/isolation", isolationSchema, { signal });
/** Read-only: a preview never deletes anything. */
export const previewDeletion = (connectionId: string | null, signal?: AbortSignal) =>
  requestJson("/api/v1/privacy/deletion-preview", deletionPreviewSchema, {
    method: "POST",
    ...jsonBody(connectionId ? { connection_id: connectionId } : {}),
    signal,
    timeoutMs: 15_000,
  });
/** Deletes exactly the previewed scope; the server refuses with 409 if it changed since. */
export const deleteImported = (expectedVersion: string, connectionId: string | null) =>
  requestJson(
    "/api/v1/privacy/delete",
    z.object({ status: z.literal("ok"), data_version: opaque }),
    {
      method: "POST",
      ...jsonBody({
        expected_version: expectedVersion,
        ...(connectionId ? { connection_id: connectionId } : {}),
      }),
      timeoutMs: 60_000,
    },
  );

const exportSchema = z.object({
  schema_version: z.literal("1.0"),
  dataset: z.literal("household"),
  exported_at: timestamp,
  data_version: opaque,
  transactions: z.array(z.unknown()),
  commitments: z.array(z.unknown()),
  revisions: z.array(z.unknown()),
});
export type ExportFile = { blob: Blob; filename: string; transactionCount: number };

/** Requests the structured export after an explicit click; contents stay in memory until saved. */
export async function exportRecords(expectedVersion: string): Promise<ExportFile> {
  const response = await apiFetch("/api/v1/privacy/export", {
    method: "POST",
    ...jsonBody({ expected_version: expectedVersion }),
    timeoutMs: 60_000,
  });
  if (!response.ok) throw await failure(response);
  const text = await response.text();
  let parsed: z.infer<typeof exportSchema>;
  try {
    parsed = exportSchema.parse(JSON.parse(text));
  } catch {
    throw new ApiError("FinBoy received an unexpected response.", response.status, {
      kind: "invalid_response",
    });
  }
  const disposition = response.headers.get("content-disposition") ?? "";
  const named = /filename="?([A-Za-z0-9._-]{1,80}\.json)"?/.exec(disposition)?.[1];
  return {
    blob: new Blob([text], { type: "application/json" }),
    filename: named ?? `finboy-export-${parsed.exported_at.slice(0, 10)}.json`,
    transactionCount: parsed.transactions.length,
  };
}

export type TaskOutcome = "evidence_opened" | "overview_explanation_opened" | "review_completed";

/** Allowlisted, content-free product outcome; failures are ignored so tasks never block on it. */
export function recordOutcome(task: TaskOutcome, subjectId?: string) {
  void requestJson("/api/v1/privacy/task-outcomes", z.object({ status: z.literal("ok") }), {
    method: "POST",
    ...jsonBody(subjectId ? { task, subject_id: subjectId } : { task }),
  }).catch(() => undefined);
}
