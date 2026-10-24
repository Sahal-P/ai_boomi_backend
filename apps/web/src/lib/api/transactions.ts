import { z } from "zod";
import { jsonBody, query, requestJson } from "./http.ts";
import {
  opaque,
  periodQuery,
  summarySchema,
  transactionSchema,
  transactionSourceSchema,
  type Category,
  type Kind,
  type Period,
  type RecordStatus,
} from "./money.ts";

const count = z.number().int().nonnegative();
const timestamp = z.iso.datetime({ offset: true });

export const decisionSchema = z.object({
  id: z.uuid(),
  action: z.string().min(1).max(40),
  created_at: timestamp,
  undone_at: timestamp.nullable(),
  can_undo: z.boolean(),
});
export type Decision = z.infer<typeof decisionSchema>;

export const detailSchema = z.object({
  transaction: transactionSchema,
  sources: z.array(transactionSourceSchema),
  confidence_factors: z.record(z.string(), z.number().nullable()),
  revisions: z.array(
    z.object({
      id: z.uuid(),
      field: z.string(),
      old_value: z.json(),
      new_value: z.json(),
      changed_by: z.enum(["user", "system"]),
      reason: z.string(),
      changed_at: timestamp,
    }),
  ),
  version: opaque,
  decisions: z.array(decisionSchema),
});
export type TransactionDetail = z.infer<typeof detailSchema>;

export const pageSchema = z.object({
  items: z.array(transactionSchema),
  total: count,
  unresolved_total: count,
  limit: z.number().int().min(1).max(200),
  offset: count,
  next_offset: count.nullable(),
  data_version: opaque,
  dataset: z.enum(["household", "quarantined"]),
});
export type TransactionPage = z.infer<typeof pageSchema>;

export type RecordScope = "all" | "month" | "unresolved";
export type RecordQuery = {
  scope: RecordScope;
  period: Period;
  status?: RecordStatus | undefined;
  category?: Category | undefined;
  source?: "gmail" | "eml_upload" | undefined;
  kind?: Kind | undefined;
  q?: string | undefined;
  dataset?: "household" | "quarantined" | undefined;
  limit: number;
  offset: number;
  /** Pins paging to a snapshot; the server answers 409 if records changed since. */
  data_version?: string | undefined;
};

export function recordQueryString(value: RecordQuery): string {
  return query({
    scope: value.scope,
    // An explicit month narrows unresolved/all scopes only when chosen; month scope needs one.
    ...(value.scope === "month" || value.period ? periodQuery(value.period) : {}),
    status: value.scope === "unresolved" ? undefined : value.status,
    category: value.category,
    source: value.source,
    kind: value.kind,
    q: value.q?.trim().slice(0, 160),
    dataset: value.dataset === "quarantined" ? "quarantined" : undefined,
    limit: value.limit,
    offset: value.offset,
    data_version: value.data_version,
  });
}

export const getTransactionPage = (value: RecordQuery, signal?: AbortSignal) =>
  requestJson(`/api/v1/transactions/page${recordQueryString(value)}`, pageSchema, { signal });

export const getTransaction = (id: string, signal?: AbortSignal) =>
  requestJson(`/api/v1/transactions/${encodeURIComponent(id)}`, detailSchema, { signal });

const candidatesSchema = z.object({
  items: z.array(transactionSchema).max(100),
  suggested_id: z.uuid().nullable(),
  data_version: opaque,
});
export type MergeCandidates = z.infer<typeof candidatesSchema>;
export const getMergeCandidates = (id: string, signal?: AbortSignal) =>
  requestJson(`/api/v1/transactions/${encodeURIComponent(id)}/merge-candidates`, candidatesSchema, {
    signal,
  });

export type Correction = {
  category?: Category;
  merchant?: string;
  amount_minor?: number;
  occurred_at?: string;
  direction?: "in" | "out";
  kind?: Kind;
};
export type DecisionAction = "confirm" | "reject" | "reopen" | "correct" | "merge" | "keep-separate";
export type DecisionRequest = {
  expected_version: string;
  action: DecisionAction;
  correction?: Correction;
  keep_id?: string;
};

export const previewSchema = z.object({
  version: opaque,
  action: z.string(),
  transaction_id: z.uuid(),
  keep_id: z.uuid().nullable(),
  source_count: count,
  affected_transaction_ids: z.array(z.uuid()),
  before_summary: summarySchema,
  after_summary: summarySchema,
});
export type DecisionPreview = z.infer<typeof previewSchema>;

export const decisionResultSchema = z.object({
  detail: detailSchema,
  decision_id: z.uuid(),
  data_version: opaque,
});
export type DecisionResult = z.infer<typeof decisionResultSchema>;

export const previewDecision = (id: string, body: DecisionRequest, signal?: AbortSignal) =>
  requestJson(`/api/v1/transactions/${encodeURIComponent(id)}/decision-preview`, previewSchema, {
    method: "POST",
    ...jsonBody(body),
    signal,
    timeoutMs: 15_000,
  });

export const decide = (id: string, body: DecisionRequest) =>
  requestJson(`/api/v1/transactions/${encodeURIComponent(id)}/decisions`, decisionResultSchema, {
    method: "POST",
    ...jsonBody(body),
    timeoutMs: 15_000,
  });

export const undoDecision = (id: string, decisionId: string, expectedVersion: string) =>
  requestJson(
    `/api/v1/transactions/${encodeURIComponent(id)}/decisions/${encodeURIComponent(decisionId)}/undo`,
    decisionResultSchema,
    { method: "POST", ...jsonBody({ expected_version: expectedVersion }), timeoutMs: 15_000 },
  );

