"use client";

import { GitMerge } from "lucide-react";
import { useState } from "react";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { LoadingPanel } from "@/components/feedback/states";
import { RecordAmount } from "@/components/records/record-bits";
import { Button } from "@/components/ui/button";
import { useAction } from "@/hooks/use-action";
import { useResource } from "@/hooks/use-resource";
import { formatMoney, type Transaction } from "@/lib/api/money";
import {
  getMergeCandidates,
  previewDecision,
  type DecisionPreview,
  type DecisionRequest,
} from "@/lib/api/transactions";
import { formatDay } from "@/lib/dates";
import { kindLabels, sourceLabels, statusLabels } from "@/lib/labels";
import { describeProblem } from "@/lib/messages";
import { cn } from "@/lib/utils";

function Facts({ row }: { row: Transaction }) {
  return (
    <dl className="space-y-1 text-xs">
      <div className="flex justify-between gap-2"><dt className="text-ink-soft">Date</dt><dd className="font-medium">{formatDay(row.occurred_at)}</dd></div>
      <div className="flex justify-between gap-2"><dt className="text-ink-soft">Amount</dt><dd className="font-medium"><RecordAmount row={row} /></dd></div>
      <div className="flex justify-between gap-2"><dt className="text-ink-soft">Type</dt><dd className="font-medium">{kindLabels[row.kind]}</dd></div>
      <div className="flex justify-between gap-2"><dt className="text-ink-soft">Status</dt><dd className="font-medium">{statusLabels[row.status]}</dd></div>
      <div className="flex justify-between gap-2"><dt className="text-ink-soft">Source emails</dt><dd className="text-right font-medium">{row.source_count} · {row.source_modes.map((mode) => sourceLabels[mode]).join(", ") || "—"}</dd></div>
    </dl>
  );
}

/**
 * Side-by-side duplicate comparison. Candidates come from the record's own compatible set
 * (confirmed records included), never from the filtered queue, and a merge is previewed first.
 */
export function MergePanel({
  tx,
  version,
  busy,
  onDecide,
}: {
  tx: Transaction;
  version: string;
  busy: boolean;
  onDecide: (request: DecisionRequest, failureTitle: string) => Promise<boolean>;
}) {
  const candidates = useResource(`candidates:${tx.id}:${version}`, (signal) => getMergeCandidates(tx.id, signal));
  const [picked, setPicked] = useState<string | null>(null);
  const [preview, setPreview] = useState<DecisionPreview | null>(null);
  const previewing = useAction();
  const items = candidates.stale ? [] : (candidates.data?.items ?? []);
  const chosenId = picked ?? candidates.data?.suggested_id ?? items[0]?.id ?? null;
  const chosen = items.find((item) => item.id === chosenId) ?? null;
  const currentPreview = preview && preview.keep_id === chosenId && preview.version === version ? preview : null;

  async function runPreview() {
    if (!chosen) return;
    const result = await previewing.run("preview", "The merge couldn't be previewed", () =>
      previewDecision(tx.id, { expected_version: version, action: "merge", keep_id: chosen.id }),
    );
    if (result) setPreview(result);
  }

  return (
    <section aria-labelledby={`merge-${tx.id}`} className="rounded-2xl border p-4">
      <h3 id={`merge-${tx.id}`} className="flex items-center gap-2 font-semibold">
        <GitMerge className="size-4 text-ink" aria-hidden="true" /> Is this the same payment as another record?
      </h3>
      {candidates.status === "loading" && <LoadingPanel className="mt-3 shadow-none" label="Finding records it could match…" />}
      {candidates.error !== null && (
        <ProblemNotice className="mt-3" problem={describeProblem(candidates.error, "Possible matches couldn't be loaded")} onRetry={candidates.reload} />
      )}
      {candidates.data && !candidates.stale && items.length === 0 && (
        <p className="mt-2 text-sm text-ink-soft">
          No compatible record to merge with. If it isn&apos;t a duplicate, keep it as its own record.
        </p>
      )}
      {items.length > 0 && (
        <>
          <fieldset className="mt-3">
            <legend className="text-xs font-semibold text-ink-soft">
              {items.length === 1 ? "Possible match" : `Choose a match (${items.length} compatible records)`}
            </legend>
            <div className="mt-2 max-h-56 space-y-1.5 overflow-y-auto">
              {items.map((item) => (
                <label key={item.id} className={cn("flex min-h-11 cursor-pointer items-center gap-3 rounded-xl border px-3 py-2 text-sm", item.id === chosenId && "border-ink bg-white/55")}>
                  <input type="radio" name={`merge-target-${tx.id}`} className="accent-ink" checked={item.id === chosenId} onChange={() => setPicked(item.id)} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium">{item.merchant}</span>
                    <span className="block text-xs text-ink-soft">
                      {formatDay(item.occurred_at)} · {statusLabels[item.status]}
                      {item.id === candidates.data?.suggested_id && " · suggested"}
                    </span>
                  </span>
                  <RecordAmount row={item} className="text-sm font-semibold" />
                </label>
              ))}
            </div>
          </fieldset>
          {chosen && (
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              <div className="rounded-xl bg-white/60 p-3 ring-1 ring-ink/[0.06]">
                <p className="mb-2 text-xs font-semibold">This record (will be merged)</p>
                <p className="mb-2 truncate text-sm font-semibold">{tx.merchant}</p>
                <Facts row={tx} />
              </div>
              <div className="rounded-xl bg-white/55 p-3">
                <p className="mb-2 text-xs font-semibold">Match (stays)</p>
                <p className="mb-2 truncate text-sm font-semibold">{chosen.merchant}</p>
                <Facts row={chosen} />
              </div>
            </div>
          )}
          {currentPreview && chosen && (
            <div role="status" className="mt-3 rounded-xl border border-ink/15 bg-white p-3 text-sm leading-relaxed">
              <p className="font-semibold">If you merge</p>
              <ul className="mt-1 list-disc space-y-0.5 pl-5 text-ink-soft">
                <li>&ldquo;{chosen.merchant}&rdquo; stays; this record&apos;s {currentPreview.source_count} source {currentPreview.source_count === 1 ? "email moves" : "emails move"} to it.</li>
                <li>{currentPreview.affected_transaction_ids.length} {currentPreview.affected_transaction_ids.length === 1 ? "record changes" : "records change"}; you can undo it from the record&apos;s history.</li>
                <li>
                  Left this month: {formatMoney(currentPreview.before_summary.estimated_unallocated_minor)} →{" "}
                  {formatMoney(currentPreview.after_summary.estimated_unallocated_minor)}
                </li>
              </ul>
            </div>
          )}
        </>
      )}
      {previewing.problem && <ProblemNotice className="mt-3" problem={previewing.problem} />}
      <div className="mt-4 flex flex-wrap gap-2">
        {chosen && !currentPreview && (
          <Button variant="outline" disabled={busy || previewing.busy !== null} onClick={() => void runPreview()}>
            {previewing.busy ? "Checking the effect…" : "Preview merge"}
          </Button>
        )}
        {chosen && currentPreview && (
          <Button
            disabled={busy}
            onClick={() =>
              void onDecide(
                { expected_version: currentPreview.version, action: "merge", keep_id: chosen.id },
                "The records weren't merged",
              )
            }
          >
            Merge into &ldquo;{chosen.merchant}&rdquo;
          </Button>
        )}
        <Button
          variant="ghost"
          disabled={busy}
          onClick={() => void onDecide({ expected_version: version, action: "keep-separate" }, "The record wasn't kept separate")}
        >
          Not a duplicate — keep both
        </Button>
      </div>
    </section>
  );
}
