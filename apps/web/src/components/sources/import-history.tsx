"use client";

import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { LoadingPanel, RefreshingLabel } from "@/components/feedback/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useResource } from "@/hooks/use-resource";
import { getImports, type ImportOutcome } from "@/lib/api/imports";
import { formatDayTime } from "@/lib/dates";
import { sourceLabels } from "@/lib/labels";
import { describeProblem } from "@/lib/messages";

export const outcomeBadges: Record<
  ImportOutcome,
  { label: string; variant: "positive" | "warning" | "destructive" | "outline" | "default" }
> = {
  queued: { label: "Queued", variant: "default" },
  running: { label: "Running", variant: "default" },
  complete: { label: "Complete", variant: "positive" },
  partial: { label: "Completed with issues", variant: "warning" },
  failed: { label: "Failed", variant: "destructive" },
  interrupted: { label: "Interrupted", variant: "destructive" },
  cancelled: { label: "Cancelled", variant: "outline" },
};

/** Durable list of active and recent imports, each with a stable status link. */
export function ImportHistory() {
  const [offset, setOffset] = useState(0);
  const imports = useResource(`imports:${offset}`, (signal) => getImports(offset, signal));
  const page = imports.stale ? null : imports.data;
  return (
    <div className="mt-3">
      {imports.status === "loading" && <LoadingPanel className="shadow-none" label="Loading imports…" />}
      <RefreshingLabel active={imports.status === "refreshing"}>Updating imports…</RefreshingLabel>
      {imports.error !== null && (
        <ProblemNotice
          problem={describeProblem(imports.error, "Import history couldn't be loaded")}
          onRetry={imports.reload}
        />
      )}
      {page && page.items.length === 0 && offset === 0 && (
        <p className="text-sm text-ink-soft">No imports yet. Scan Gmail or upload emails to start.</p>
      )}
      {page && page.items.length > 0 && (
        <ul className="divide-y">
          {page.items.map((run) => {
            const badge = outcomeBadges[run.outcome];
            return (
              <li key={run.id}>
                <Link
                  href={`/import/${run.id}`}
                  className="flex min-h-14 items-center gap-3 py-3 hover:bg-canvas/70"
                >
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold">{sourceLabels[run.mode]}</p>
                    <p className="text-xs text-ink-soft">
                      {run.started_at ? formatDayTime(run.started_at) : "Not started yet"}
                      {run.transactions_created > 0 && ` · ${run.transactions_created} new`}
                      {run.failed > 0 && ` · ${run.failed} unread`}
                    </p>
                  </div>
                  <Badge variant={badge.variant}>{badge.label}</Badge>
                  <ChevronRight className="size-4 shrink-0 text-ink-soft" aria-hidden="true" />
                </Link>
              </li>
            );
          })}
        </ul>
      )}
      {page && (offset > 0 || page.next_offset !== null) && (
        <div className="mt-3 flex flex-wrap items-center justify-between gap-2">
          <Button
            variant="ghost"
            size="sm"
            disabled={offset === 0}
            onClick={() => setOffset(Math.max(0, offset - 20))}
          >
            Newer
          </Button>
          <p className="text-xs text-ink-soft">{page.total} imports</p>
          <Button
            variant="ghost"
            size="sm"
            disabled={page.next_offset === null}
            onClick={() => page.next_offset !== null && setOffset(page.next_offset)}
          >
            Older
          </Button>
        </div>
      )}
    </div>
  );
}
