"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { count, moment, Pager, RefreshButton } from "@/components/admin/admin-bits";
import { PageHeader } from "@/components/app-shell/page-header";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { LoadingPanel, RefreshingLabel } from "@/components/feedback/states";
import { useQueryUpdate } from "@/hooks/use-query-update";
import { useResource } from "@/hooks/use-resource";
import { auditLabels, label, readable } from "@/lib/admin-labels";
import { getAudit, type AuditRow } from "@/lib/api/admin";
import { describeProblem } from "@/lib/messages";

const VIA: Record<string, string> = {
  server: "on the server",
  self_serve: "self-serve household",
  pilot: "village pilot household",
  pending: "pending sign-up",
};

/** The allowlisted details in words: days, payment, admin, removed, via, outcome. */
function details(row: AuditRow): string[] {
  const parts: string[] = [];
  for (const [key, value] of Object.entries(row.detail)) {
    if (key === "days") parts.push(`${value} ${value === 1 ? "day" : "days"}`);
    else if (key === "removed") parts.push(`${value} removed`);
    else if (key === "via" && typeof value === "string") parts.push(VIA[value] ?? readable(value));
    else if ((key === "payment" || key === "admin") && typeof value === "string") parts.push(`${key} ${value.slice(0, 8)}`);
    else parts.push(`${readable(key)}: ${value}`);
  }
  return parts;
}

function who(row: AuditRow): string {
  if (row.admin_email) return row.admin_email;
  return row.detail.via === "server" ? "Server" : "Unknown email";
}

/** Who did what, to which household and when. Read-only; nothing here can be changed. */
export function AuditScreen() {
  const params = useSearchParams();
  const update = useQueryUpdate();
  const offsetParam = Number(params.get("offset") ?? 0);
  const offset = Number.isInteger(offsetParam) && offsetParam > 0 ? offsetParam : 0;
  const audit = useResource(`admin-audit:${offset}`, (signal) => getAudit(offset, signal));
  const page = audit.stale ? null : audit.data;
  return (
    <div className="space-y-5">
      <PageHeader
        title="Audit log"
        description="Every admin sign-in and action, newest first. Entries stay after a household is erased."
        actions={<RefreshButton resource={audit} />}
      />
      <RefreshingLabel active={audit.status === "refreshing"}>Updating…</RefreshingLabel>
      {audit.status === "loading" && <LoadingPanel label="Loading the audit log…" />}
      {audit.error !== null && (
        <ProblemNotice
          problem={describeProblem(audit.error, audit.data ? "Couldn't refresh — showing the last loaded entries" : "The audit log couldn't be loaded")}
          onRetry={audit.reload}
        />
      )}
      {page && (
        <section aria-labelledby="audit-title">
          <h2 id="audit-title" className="text-base font-semibold">
            {count(page.total)} {page.total === 1 ? "entry" : "entries"}
          </h2>
          {page.items.length === 0 ? (
            <p className="mt-2 text-sm text-ink-soft">Nothing has been recorded yet.</p>
          ) : (
            <ol aria-label="Audit entries" className="mt-3 space-y-2">
              {page.items.map((row) => (
                <li key={row.id} className="surface rounded-lg px-4 py-3">
                  <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-0.5">
                    <p className="text-sm font-semibold">{label(auditLabels, row.action)}</p>
                    <time className="text-xs text-ink-soft" dateTime={row.created_at}>
                      {moment(row.created_at)}
                    </time>
                  </div>
                  <p className="mt-0.5 text-xs break-all text-ink-soft">
                    {who(row)}
                    {row.short_id && row.household_id && (
                      <>
                        {" · household "}
                        <Link
                          href={`/admin/households?selected=${row.household_id}`}
                          className="font-mono font-semibold text-ink underline underline-offset-4"
                        >
                          {row.short_id}
                        </Link>
                      </>
                    )}
                    {details(row).map((part) => ` · ${part}`)}
                  </p>
                </li>
              ))}
            </ol>
          )}
          <Pager
            label="Audit pages"
            offset={page.offset}
            shown={page.items.length}
            total={page.total}
            nextOffset={page.next_offset}
            onPage={(next) => update({ offset: next ? String(next) : null })}
          />
        </section>
      )}
    </div>
  );
}
