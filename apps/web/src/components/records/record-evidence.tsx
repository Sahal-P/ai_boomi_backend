import { FileText, ImageIcon, Mail, Mic, PencilLine } from "lucide-react";
import { formatMoney, type TransactionSource } from "@/lib/api/money";
import type { TransactionDetail } from "@/lib/api/transactions";
import { formatDay, formatDayTime } from "@/lib/dates";
import { confidenceFactorLabels, evidenceFieldLabel, sourceLabels, sourceSender } from "@/lib/labels";

/** A Google Pay statement row: what the statement printed, its UPI transaction ID and account. */
function StatementCard({ source, detail }: { source: TransactionSource; detail: TransactionDetail }) {
  const { bank, page, row, detail: printed } = source.evidence;
  const received = source.event_type === "credit";
  return (
    <li className="rounded-2xl border p-4">
      <p className="flex items-center gap-2 text-sm font-semibold">
        <FileText className="size-4 shrink-0 text-ink" aria-hidden="true" />
        {sourceSender(source)}
      </p>
      <p className="mt-1 text-xs text-ink-soft">
        {sourceLabels[source.source]}
        {page ? ` · page ${page}${row ? `, row ${row}` : ""}` : ""} · read by a fixed rule
      </p>
      <p className="mt-2 text-xs text-ink-soft">
        The statement shows {formatMoney(source.amount_minor)} {received ? "received from" : "paid to"}{" "}
        {source.merchant ?? "this payee"}
        {source.occurred_at ? ` on ${formatDayTime(source.occurred_at)}` : ""}.
      </p>
      <dl className="mt-3 grid gap-2 text-xs leading-relaxed sm:grid-cols-2">
        {printed && (
          <div className="sm:col-span-2">
            <dt className="font-semibold text-ink-soft">As printed</dt>
            <dd className="break-words">&ldquo;{printed}&rdquo;</dd>
          </div>
        )}
        {detail.transaction.reference_id && (
          <div>
            <dt className="font-semibold text-ink-soft">UPI transaction ID</dt>
            <dd className="break-all tabular-nums">{detail.transaction.reference_id}</dd>
          </div>
        )}
        {bank && (
          <div>
            <dt className="font-semibold text-ink-soft">{received ? "Paid into" : "Paid from"}</dt>
            <dd>
              {bank}
              {detail.transaction.account_last4 ? ` ••${detail.transaction.account_last4}` : ""}
            </dd>
          </div>
        )}
      </dl>
    </li>
  );
}

function SourceCard({ source }: { source: TransactionSource }) {
  const entries = Object.entries(source.evidence);
  const screenshot = source.source === "whatsapp_image";
  const voice = source.source === "whatsapp_voice";
  const typed = source.source === "manual_entry";
  const Icon = screenshot ? ImageIcon : voice ? Mic : typed ? PencilLine : Mail;
  return (
    <li className="rounded-2xl border p-4">
      <p className="flex items-center gap-2 text-sm font-semibold">
        <Icon className="size-4 shrink-0 text-ink" aria-hidden="true" />
        <span className="break-all">{sourceSender(source)}</span>
      </p>
      <p className="mt-1 text-xs text-ink-soft">
        {sourceLabels[source.source]} · received {formatDayTime(source.received_at)}
        {source.extraction_method === "llm" ? " · read with AI assistance" : " · read by a fixed rule"}
      </p>
      <p className="mt-2 text-xs text-ink-soft">
        {screenshot
          ? "This screenshot shows"
          : voice
            ? "Your voice note says"
            : typed
              ? "You added"
              : "This email says"}{" "}
        {formatMoney(source.amount_minor)}
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

/** The source notifications behind a record. Snippets are bounded and redacted by the server. */
export function RecordEvidence({ detail }: { detail: TransactionDetail }) {
  const factors = Object.entries(detail.confidence_factors);
  const only = (mode: TransactionSource["source"]) =>
    detail.sources.length > 0 && detail.sources.every((source) => source.source === mode);
  const screenshots = only("whatsapp_image");
  const voices = only("whatsapp_voice");
  const typed = only("manual_entry");
  const statements = only("gpay_statement");
  const whatsapp = detail.sources.some((source) => source.source.startsWith("whatsapp_"));
  const mixed = whatsapp && !screenshots && !voices;
  const noun = screenshots
    ? "screenshot"
    : voices
      ? "voice note"
      : typed
        ? "entry"
        : statements
          ? "statement row"
          : mixed
          ? "notification"
          : "email";
  return (
    <section aria-label="Evidence">
      <h3 className="font-semibold">Evidence</h3>
      <p className="mt-1 text-xs text-ink-soft">
        {detail.sources.length} source {detail.sources.length === 1 ? noun : `${noun}s`}. Your
        corrections never change what the {noun}s {screenshots || mixed ? "showed" : "said"}.
      </p>
      <ul className="mt-3 space-y-3">
        {detail.sources.map((source) =>
          source.source === "gpay_statement" ? (
            <StatementCard key={source.id} source={source} detail={detail} />
          ) : (
            <SourceCard key={source.id} source={source} />
          ),
        )}
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
