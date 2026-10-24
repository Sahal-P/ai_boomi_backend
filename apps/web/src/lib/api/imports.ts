import { z } from "zod";
import { emitSessionEvent } from "../session-events.ts";
import { ApiError, apiBaseUrl, jsonBody, query, requestJson } from "./http.ts";
import { dayOrTime, opaque, sourceModeSchema } from "./money.ts";

const counter = z.number().int().nonnegative();
const timestamp = z.iso.datetime({ offset: true });
const retryStrategy = z.enum(["refetch_gmail", "select_original_files", "none"]);
export type RetryStrategy = z.infer<typeof retryStrategy>;

export const importRunSchema = z.object({
  id: z.uuid(),
  mode: sourceModeSchema,
  status: z.enum(["queued", "running", "completed", "failed"]),
  headers_checked: counter,
  candidates_found: counter,
  emails_processed: counter,
  events_extracted: counter,
  transactions_created: counter,
  duplicates_merged: counter,
  needs_review: counter,
  non_financial_skipped: counter,
  failed: counter,
  error_code: z.string().max(64).nullable(),
  started_at: timestamp.nullable(),
  finished_at: timestamp.nullable(),
  outcome: z.enum(["queued", "running", "complete", "partial", "failed", "interrupted", "cancelled"]),
  retryable: z.boolean(),
  retry_strategy: retryStrategy,
  cancel_requested: z.boolean(),
  window_start: dayOrTime.nullable(),
  window_end: dayOrTime.nullable(),
  truncated: z.boolean(),
  data_version: opaque,
  /** v1.1: a truncated Gmail scan can continue its original window as a new bounded job. */
  can_continue: z.boolean(),
});
export type ImportRun = z.infer<typeof importRunSchema>;
export type ImportOutcome = ImportRun["outcome"];

const listSchema = z.object({
  items: z.array(importRunSchema),
  total: counter,
  next_offset: counter.nullable(),
});
export type ImportList = z.infer<typeof listSchema>;

export const issueSchema = z.object({
  id: z.uuid(),
  source_id: z.uuid(),
  source_mode: sourceModeSchema,
  reason: z.enum(["extraction_failed", "no_supported_events", "message_unavailable"]),
  retryable: z.boolean(),
  retry_strategy: retryStrategy,
  attempts: counter,
});
export type ImportIssue = z.infer<typeof issueSchema>;
const issueListSchema = z.object({
  items: z.array(issueSchema),
  total: counter,
  next_offset: counter.nullable(),
});

const startedSchema = z.object({ import_run_id: z.uuid() });

export const isActive = (run: Pick<ImportRun, "outcome">) =>
  run.outcome === "queued" || run.outcome === "running";

export const getImportRun = (id: string, signal?: AbortSignal) =>
  requestJson(`/api/v1/imports/${encodeURIComponent(id)}`, importRunSchema, { signal });
export const getImports = (offset: number, signal?: AbortSignal) =>
  requestJson(`/api/v1/imports${query({ limit: 20, offset })}`, listSchema, { signal });
export const getImportIssues = (id: string, offset: number, signal?: AbortSignal) =>
  requestJson(
    `/api/v1/imports/${encodeURIComponent(id)}/issues${query({ limit: 50, offset })}`,
    issueListSchema,
    { signal },
  );
export const retryImport = (id: string, expectedVersion: string, sourceIds?: string[]) =>
  requestJson(`/api/v1/imports/${encodeURIComponent(id)}/retry`, startedSchema, {
    method: "POST",
    ...jsonBody({
      expected_version: expectedVersion,
      ...(sourceIds ? { source_ids: sourceIds.slice(0, 50) } : {}),
    }),
    timeoutMs: 15_000,
  });
export const continueImport = (id: string, expectedVersion: string) =>
  requestJson(`/api/v1/imports/${encodeURIComponent(id)}/continue`, startedSchema, {
    method: "POST",
    ...jsonBody({ expected_version: expectedVersion }),
    timeoutMs: 15_000,
  });
export const cancelImport = (id: string, expectedVersion: string) =>
  requestJson(`/api/v1/imports/${encodeURIComponent(id)}/cancel`, importRunSchema, {
    method: "POST",
    ...jsonBody({ expected_version: expectedVersion }),
  });

export const UPLOAD_LIMITS = { files: 50, bytesPerFile: 2 * 1024 * 1024 } as const;
export type FileProblem = "not_eml" | "empty" | "too_large";

/** Local check mirroring the server's all-or-nothing validation; nothing leaves the device. */
export function fileProblem(file: Pick<File, "name" | "size" | "type">): FileProblem | null {
  if (!file.name.toLowerCase().endsWith(".eml")) return "not_eml";
  if (!["", "message/rfc822", "application/octet-stream"].includes(file.type)) return "not_eml";
  if (file.size === 0) return "empty";
  if (file.size > UPLOAD_LIMITS.bytesPerFile) return "too_large";
  return null;
}

/**
 * Uploads a validated batch. XMLHttpRequest is used only because fetch cannot report
 * upload progress; credentials, envelope parsing and session expiry match requestJson.
 */
export function uploadEml(
  files: File[],
  options: { signal?: AbortSignal; onProgress?: (fraction: number) => void } = {},
): Promise<{ import_run_id: string }> {
  if (
    !files.length ||
    files.length > UPLOAD_LIMITS.files ||
    files.some((file) => fileProblem(file) !== null)
  ) {
    return Promise.reject(
      new ApiError("Choose 1–50 .eml files, up to 2 MB each.", undefined, { kind: "validation" }),
    );
  }
  const base = apiBaseUrl();
  const body = new FormData();
  for (const file of files) {
    body.append("files", new File([file], file.name, { type: "message/rfc822" }));
  }
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", `${base}/api/v1/imports/eml`);
    request.withCredentials = false;
    request.timeout = 120_000;
    request.setRequestHeader("Accept", "application/json");
    request.responseType = "text";
    const abort = () => request.abort();
    options.signal?.addEventListener("abort", abort, { once: true });
    request.upload.onprogress = (event) => {
      if (event.lengthComputable && event.total > 0) options.onProgress?.(event.loaded / event.total);
    };
    request.onabort = () => reject(new DOMException("Upload cancelled", "AbortError"));
    request.ontimeout = () =>
      reject(new ApiError("FinBoy took too long to respond.", undefined, { kind: "timeout" }));
    request.onerror = () =>
      reject(
        new ApiError("FinBoy could not be reached.", undefined, {
          kind: navigator.onLine === false ? "offline" : "network",
        }),
      );
    request.onload = () => {
      options.signal?.removeEventListener("abort", abort);
      let payload: unknown;
      try {
        payload = JSON.parse(request.responseText);
      } catch {
        payload = null;
      }
      if (request.status >= 200 && request.status < 300) {
        const parsed = startedSchema.safeParse(payload);
        if (parsed.success) resolve(parsed.data);
        else
          reject(
            new ApiError("FinBoy received an unexpected response.", request.status, {
              kind: "invalid_response",
            }),
          );
        return;
      }
      const envelope = z
        .object({
          error: z.object({
            code: z.string().regex(/^[a-z0-9_.-]{1,64}$/),
            request_id: z
              .string()
              .regex(/^[A-Za-z0-9-]{1,64}$/)
              .optional(),
          }),
        })
        .safeParse(payload);
      if (request.status === 401) emitSessionEvent("expired");
      reject(
        new ApiError("FinBoy could not complete the request.", request.status, {
          code: envelope.success ? envelope.data.error.code : undefined,
          requestId: envelope.success ? envelope.data.error.request_id : undefined,
        }),
      );
    };
    request.send(body);
  });
}
