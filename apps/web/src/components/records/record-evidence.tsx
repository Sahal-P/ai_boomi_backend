import { Mail } from "lucide-react";
import { formatMoney, type TransactionSource } from "@/lib/api/money";
import type { TransactionDetail } from "@/lib/api/transactions";
import { formatDay, formatDayTime } from "@/lib/dates";
import { confidenceFactorLabels, evidenceFieldLabel, sourceLabels } from "@/lib/labels";

function SourceCard({ source }: { source: TransactionSource }) {
  const entries = Object.entries(source.evidence);
  return (
    <li className="rounded-2xl border p-4">
      <p className="flex items-center gap-2 text-sm font-semibold">
        <Mail className="size-4 shrink-0 text-violet-deep" aria-hidden="true" />
        <span className="break-all">{source.sender_domain}</span>
      </p>
      <p className="mt-1 text-xs text-ink-soft">
        {sourceLabels[source.source]} · received {formatDayTime(source.received_at)}
        {source.extraction_method === "llm" ? " · read with AI assistance" : " · read by a fixed rule"}
      </p>
      <p className="mt-2 text-xs text-ink-soft">
        This email says {formatMoney(source.amount_minor)}
        {source.merchant ? ` at ${source.merchant}` : ""}
        {source.occurred_at ? ` on ${formatDay(source.occurred_at)}` : ""}
        {source.due_date ? `, due ${formatDay(source.due_date)}` : ""}.
      </p>
      {entries.length > 0 && (
        <dl className="mt-3 space-y-2">
          {entries.map(([key, value]) => (
            <div key={key} className="text-xs leading-relaxed">
              <dt className="font-semibold text-ink-soft">{evidenceFieldLabel(key)}</dt>
              <dd className="break-words">&ldquo;{value}&rdquo;</dd>
            </div>
          ))}
        </dl>
      )}
    </li>
  );
}

/** The source emails behind a record. Snippets are bounded and redacted by the server. */
export function RecordEvidence({ detail }: { detail: TransactionDetail }) {
  const factors = Object.entries(detail.confidence_factors);
  return (
    <section aria-label="Evidence">
      <h3 className="font-semibold">Evidence</h3>
      <p className="mt-1 text-xs text-ink-soft">
        {detail.sources.length} source {detail.sources.length === 1 ? "email" : "emails"}. Your
        corrections never change what the emails said.
      </p>
      <ul className="mt-3 space-y-3">
        {detail.sources.map((source) => (
          <SourceCard key={source.id} source={source} />
        ))}
      </ul>
      {factors.length > 0 && (
        <details className="mt-3 rounded-xl border p-3 text-xs">
          <summary className="cursor-pointer font-semibold">How FinBoy read this</summary>
          <p className="mt-2 text-ink-soft">
            Signals about how cleanly details were read. They describe extraction, not whether
            money actually moved.
          </p>
          <dl className="mt-2 space-y-1.5">
            {factors.map(([key, value]) => (
              <div key={key} className="flex justify-between gap-3">
                <dt>{confidenceFactorLabels[key] ?? "Other signal"}</dt>
                <dd className="font-medium">
                  {value === null ? "Not applicable" : key === "source_count" ? value : value > 0 ? "Yes" : "No"}
                </dd>
              </div>
            ))}
          </dl>
        </details>
      )}
    </section>
  );
}
