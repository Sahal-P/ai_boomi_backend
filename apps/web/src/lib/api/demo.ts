import { z } from "zod";
import { requestJson } from "./http.ts";
import { commitmentSchema, demoSummarySchema, transactionSchema } from "./money.ts";

/** Read-only synthetic sample. It never writes household imports, records or history. */
export const demoSchema = z.object({
  dataset: z.literal("demo"),
  read_only: z.literal(true),
  as_of: z.iso.date(),
  summary: demoSummarySchema,
  transactions: z.array(transactionSchema),
  commitments: z.array(commitmentSchema),
});
export type DemoData = z.infer<typeof demoSchema>;

export const getDemo = (signal?: AbortSignal) =>
  requestJson("/api/v1/demo", demoSchema, { signal });
