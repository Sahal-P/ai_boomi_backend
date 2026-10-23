import Link from "next/link";
import { CircleCheck, CircleDashed, LoaderCircle, TriangleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { ImportRun } from "@/lib/api/mail";
import { oauthErrorMessage } from "@/lib/api/mail";
import { MailAlert, MailFrame } from "./mail-frame";

export function ImportScreen({ run, error, onRetry }: {
  run: ImportRun | null; error: string | null; onRetry: () => void;
}) {
  const completed = run?.status === "completed";
  const failed = run?.status === "failed";
  const rows = [
    { value: run?.headers_checked ?? 0, label: "email headers checked" },
    { value: run?.candidates_found ?? 0, label: "possible financial emails" },
    { value: run?.transactions_created ?? 0, label: "transactions extracted" },
    { value: run?.duplicates_merged ?? 0, label: "duplicates merged" },
    { value: run?.needs_review ?? 0, label: "need your confirmation", review: true },
  ];
  return <MailFrame eyebrow="Following the trail"
    title={completed ? "Your money story is taking shape." : failed ? "This import needs another look." : "A clearer picture, one email at a time."}
    description="FinBoy checks possible financial emails, links duplicate notifications, and flags uncertainty for you to review.">
    {error && <MailAlert message={error} onRetry={onRetry} />}
    {failed && <MailAlert message={oauthErrorMessage(run.error_code ?? "import_failed") ?? "The import stopped. Please try again."} />}
    <div className="max-w-2xl rounded-2xl border bg-card p-6 sm:p-8" aria-busy={!error && !completed && !failed}>
      <div className="mb-7 flex items-center gap-3 border-b pb-5 text-sm font-medium text-primary" role="status">
        {completed ? <CircleCheck className="size-5" /> : failed || error ? <TriangleAlert className="size-5" /> : <LoaderCircle className="size-5 motion-safe:animate-spin" />}
        {error ? "Connection interrupted · progress saved" : completed ? "Import complete" : failed ? "Import stopped · partial progress saved" : run?.status === "running" ? "Import in progress" : "Preparing your import…"}
      </div>
      <ul className="space-y-6" aria-label="Import progress">
        {rows.map((row) => {
          const Icon = row.review && row.value ? TriangleAlert : completed || row.value ? CircleCheck : CircleDashed;
          return <li key={row.label} className="flex items-center gap-3">
            <Icon className={`size-5 shrink-0 ${row.review && row.value ? "text-amber-700" : "text-primary"}`} aria-hidden="true" />
            <span className="text-sm sm:text-base"><strong className="font-semibold tabular-nums">{row.value}</strong> {row.label}</span>
          </li>;
        })}
      </ul>
      {run && <p className="mt-7 text-xs text-muted-foreground">{run.emails_processed} processed · {run.non_financial_skipped} non-financial skipped · {run.failed} could not be extracted</p>}
    </div>
    {(completed || failed) && <div className="mt-6 flex flex-wrap gap-3">
      <Button asChild className="h-11 px-5"><Link href="/dashboard">Go to dashboard</Link></Button>
      <Button asChild variant="outline" className="h-11 px-5"><Link href="/review">Review uncertain items</Link></Button>
      {failed && <Button asChild variant="ghost" className="h-11"><Link href="/connect">Start another import</Link></Button>}
    </div>}
    <p className="mt-6 max-w-xl text-xs leading-relaxed text-muted-foreground">Based on email-derived and confirmed records. Your actual bank balance may differ.</p>
  </MailFrame>;
}
