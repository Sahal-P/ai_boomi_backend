"use client";

import { LoaderCircle, Pause, Play, Square, Volume2 } from "lucide-react";
import Link from "next/link";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { RecordAmount } from "@/components/records/record-bits";
import { Button } from "@/components/ui/button";
import type { Playback } from "@/hooks/use-speech";
import { displayLang, SPEECH_LIMITS, type DisplayStyle } from "@/lib/api/assistant";
import { formatMoney } from "@/lib/api/money";
import { recordOutcome } from "@/lib/api/privacy";
import type { Turn } from "@/lib/conversation";
import { answerCopy, answerDate, answerPeriod } from "@/lib/answer-copy";
import { kindLabels } from "@/lib/labels";

export const styleLabels: Record<DisplayStyle, { label: string; lang?: string }> = {
  auto: { label: "Match my question" },
  en: { label: "English" },
  hi: { label: "हिन्दी", lang: "hi" },
  hinglish: { label: "Hinglish" },
  ml: { label: "മലയാളം", lang: "ml" },
  manglish: { label: "Manglish" },
};

/** A submitted question paired with its own result, scope and reply style. */
export function TurnCard({
  turn,
  currentStyle,
  playback,
  onPlay,
  onResume,
  onStop,
  onRetry,
  onCancel,
  onAskAgain,
  busy,
}: {
  turn: Turn;
  currentStyle: DisplayStyle;
  playback: Playback;
  onPlay: () => void;
  onResume: () => void;
  onStop: () => void;
  onRetry: () => void;
  onCancel: () => void;
  onAskAgain: () => void;
  busy: boolean;
}) {
  const answer = turn.answer;
  const mine = playback.turnId === turn.id;
  const lang = answer ? displayLang(answer) : undefined;
  const copy = answerCopy(answer ?? { display_language: "en", display_script: "Latn" });
  return (
    <article aria-label={`Question: ${turn.question}`} className="surface rounded-3xl p-5 sm:p-7">
      <header className="border-b pb-4">
        <p className="text-xs font-semibold text-ink-soft">
          You asked · reply style {styleLabels[turn.style].label}
        </p>
        <p className="mt-1 text-base font-medium break-words whitespace-pre-line">{turn.question}</p>
      </header>

      {turn.state === "pending" && (
        <div className="mt-4 flex flex-wrap items-center gap-3 text-sm">
          <LoaderCircle className="size-4 text-violet-deep motion-safe:animate-spin" aria-hidden="true" />
          <span>Thinking through your question… this can take up to a minute.</span>
          <Button size="sm" variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
        </div>
      )}
      {turn.state === "cancelled" && (
        <div className="mt-4 flex flex-wrap items-center gap-3 text-sm text-ink-soft">
          <span>You cancelled this question. Nothing was saved.</span>
          <Button size="sm" variant="outline" disabled={busy} onClick={onRetry}>
            Ask it again
          </Button>
        </div>
      )}
      {turn.state === "failed" && turn.problem && (
        <ProblemNotice className="mt-4" problem={turn.problem} onRetry={busy ? undefined : onRetry} retryLabel="Ask again" />
      )}

      {answer && turn.state === "answered" && (
        <div className="mt-4 space-y-5" lang={lang}>
          <div className="flex flex-wrap items-center gap-2 text-xs font-semibold">
            <span className="rounded-full bg-lilac px-2.5 py-1 text-violet-deep">{copy[answer.policy]}</span>
            {answer.resolved_period && (
              // The API's period label is an ISO range; show the product's one date style instead.
              <span className="rounded-full bg-muted px-2.5 py-1 text-ink-soft">
                {answerPeriod(answer.resolved_period.start, answer.resolved_period.end, copy.locale)}
              </span>
            )}
          </div>
          <p lang={lang} className="text-lg leading-relaxed whitespace-pre-line text-ink">
            {answer.display_text}
          </p>
          {answer.facts.length > 0 && (
            <dl className="grid gap-3 sm:grid-cols-2" lang={lang}>
              {answer.facts.map((fact) => (
                <div key={fact.key} className="rounded-2xl bg-canvas p-4">
                  <dt className="text-xs text-ink-soft">{fact.label}</dt>
                  <dd className="mt-1 text-lg font-semibold tabular-nums">
                    {fact.amount_minor !== null ? formatMoney(fact.amount_minor) : (fact.count ?? "—")}
                  </dd>
                </div>
              ))}
            </dl>
          )}
          {answer.warnings.length > 0 && (
            <ul className="list-disc space-y-1 pl-5 text-sm text-amber-900" lang={lang}>
              {answer.warnings.map((warning) => (
                <li key={warning}>{answer.warning_labels[warning] ?? "Some records may be missing or unverified."}</li>
              ))}
            </ul>
          )}
          {answer.evidence_transactions.length > 0 && (
            <section aria-label={copy.evidence}>
              <h3 className="text-sm font-semibold">
                {copy.evidence}
                <span className="font-normal text-ink-soft">
                  {answer.evidence_sampled
                    ? ` · ${copy.showing} ${answer.evidence_transactions.length} ${copy.of} ${answer.evidence_total} — ${copy.sample}`
                    : ` · ${copy.all} ${answer.evidence_transactions.length}`}
                </span>
              </h3>
              <ul className="mt-2 divide-y rounded-2xl border">
                {answer.evidence_transactions.map((tx) => (
                  <li key={tx.id}>
                    <Link
                      href={`/transactions?selected=${tx.id}`}
                      onClick={() => recordOutcome("evidence_opened", tx.id)}
                      className="flex items-center justify-between gap-3 px-4 py-3 text-sm hover:bg-canvas"
                    >
                      <span className="min-w-0">
                        <span className="block font-semibold break-words text-violet-deep underline underline-offset-4">{tx.merchant}</span>
                        <span className="block text-xs text-ink-soft">
                          {answerDate(tx.occurred_at, copy.locale)} · <span lang="en">{kindLabels[tx.kind]}</span>
                          {tx.source_count ? ` · ${tx.source_count} ${tx.source_count === 1 ? "email" : "emails"}` : ""}
                        </span>
                      </span>
                      <RecordAmount row={tx} className="shrink-0 font-semibold" />
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <div className="flex flex-wrap items-center gap-2 border-t pt-4">
            {answer.speech_text.length > SPEECH_LIMITS.characters ? (
              <p className="text-xs text-ink-soft">{copy.tooLong}</p>
            ) : mine && playback.step === "preparing" ? (
              <>
                <Button variant="outline" disabled>
                  <LoaderCircle className="motion-safe:animate-spin" aria-hidden="true" /> {copy.preparing}
                </Button>
                <Button variant="ghost" onClick={onStop}>{copy.cancel}</Button>
              </>
            ) : mine && playback.step === "playing" ? (
              <Button variant="outline" onClick={onStop}>
                <Square aria-hidden="true" /> {copy.stop}
              </Button>
            ) : mine && playback.step === "ready" ? (
              <Button onClick={onResume}>
                <Play aria-hidden="true" /> {copy.ready}
              </Button>
            ) : (
              <Button variant="outline" onClick={onPlay}>
                <Volume2 aria-hidden="true" /> {mine && playback.step === "failed" ? copy.retry : copy.play}
              </Button>
            )}
            {turn.style !== currentStyle && (
              <Button variant="ghost" disabled={busy} onClick={onAskAgain}>
                Ask again in {styleLabels[currentStyle].label}
              </Button>
            )}
          </div>
          <div role="status" aria-live="polite" className="text-sm">
            {mine && playback.step === "playing" && (
              <p className="flex items-center gap-2 text-ink-soft">
                <Pause className="size-4" aria-hidden="true" /> {copy.playing}
              </p>
            )}
          </div>
          {mine && playback.step === "failed" && <ProblemNotice problem={playback.problem} />}
        </div>
      )}
    </article>
  );
}
