import { ImageIcon, Mail, Mic, PencilLine } from "lucide-react";
import { formatMoney, type TransactionSource } from "@/lib/api/money";
import type { TransactionDetail } from "@/lib/api/transactions";
import { formatDay, formatDayTime } from "@/lib/dates";
import { confidenceFactorLabels, evidenceFieldLabel, sourceLabels, sourceSender } from "@/lib/labels";

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
  const whatsapp = detail.sources.some((source) => source.source.startsWith("whatsapp_"));
  const mixed = whatsapp && !screenshots && !voices;
  const noun = screenshots
    ? "screenshot"
    : voices
      ? "voice note"
      : typed
        ? "entry"
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
