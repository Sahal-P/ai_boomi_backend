import { CalendarRange, CircleAlert, CircleCheck, CircleHelp, Clock3, ShieldAlert } from "lucide-react";
import Link from "next/link";
import type { Coverage } from "@/lib/api/money";
import { formatDayTime, formatRange } from "@/lib/dates";
import { cn } from "@/lib/utils";

const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`;

/** Freshness and coverage of the ledger — separate from whether the service is reachable. */
export function coverageHeadline(coverage: Coverage): { label: string; tone: "ok" | "warn" | "unknown" } {
  if (coverage.state === "unknown") return { label: "Coverage unknown", tone: "unknown" };
  if (coverage.state === "partial" || coverage.truncated) return { label: "Partly scanned", tone: "warn" };
  return { label: "Scanned window complete", tone: "ok" };
}

export function CoverageSummary({ coverage, className }: { coverage: Coverage; className?: string }) {
  const headline = coverageHeadline(coverage);
  const window = formatRange(coverage.window_start, coverage.window_end);
  const Icon = headline.tone === "ok" ? CircleCheck : headline.tone === "warn" ? CircleAlert : CircleHelp;
  return (
    <div className={cn("space-y-3 text-sm", className)}>
      <p className="flex items-center gap-2 font-semibold">
        <Icon
          className={cn(
            "size-4 shrink-0",
            headline.tone === "ok" ? "text-positive" : headline.tone === "warn" ? "text-amber-800" : "text-ink-soft",
          )}
          aria-hidden="true"
        />
        {headline.label}
      </p>
      <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
        <div className="flex gap-2">
          <Clock3 className="mt-0.5 size-4 shrink-0 text-ink-soft" aria-hidden="true" />
          <div>
            <dt className="text-xs text-ink-soft">Last successful scan</dt>
            <dd className="font-medium">
              {coverage.last_successful_scan_at
                ? formatDayTime(coverage.last_successful_scan_at)
                : "No successful scan yet"}
            </dd>
          </div>
        </div>
        <div className="flex gap-2">
          <CalendarRange className="mt-0.5 size-4 shrink-0 text-ink-soft" aria-hidden="true" />
          <div>
            <dt className="text-xs text-ink-soft">Emails checked from</dt>
            <dd className="font-medium">{window ?? "Unknown"}</dd>
          </div>
        </div>
      </dl>
      <ul className="space-y-1.5 text-ink-soft">
        <li>Scans run only when you start one — nothing syncs in the background.</li>
        {coverage.state === "unknown" && (
          <li>Without a completed scan FinBoy can&apos;t say which emails are covered.</li>
        )}
        {coverage.failed_source_count > 0 && (
          <li className="text-amber-900">
            {plural(coverage.failed_source_count, "email", "emails")} couldn&apos;t be read and
            aren&apos;t included.
          </li>
        )}
        {coverage.truncated && (
          <li className="text-amber-900">
            The last scan reached its limit, so older emails in the window weren&apos;t checked.
            Scan again from Sources to continue.
          </li>
        )}
        <li>A scanned window covers those emails only — it isn&apos;t a bank balance.</li>
      </ul>
      {(coverage.active_import_id || coverage.quarantined_count > 0) && (
        <div className="flex flex-wrap gap-x-5 gap-y-2 text-sm font-semibold">
          {coverage.active_import_id && (
            <Link
              href={`/import/${coverage.active_import_id}`}
              className="text-ink underline underline-offset-4"
            >
              Import in progress — view it
            </Link>
          )}
          {coverage.quarantined_count > 0 && (
            <Link
              href="/transactions?dataset=quarantined&scope=all"
              className="inline-flex items-center gap-1.5 text-ink underline underline-offset-4"
            >
              <ShieldAlert className="size-4" aria-hidden="true" />
              {plural(coverage.quarantined_count, "record is", "records are")} on hold
            </Link>
          )}
        </div>
      )}
    </div>
  );
}
