"use client";

import { Check, ChevronDown, Copy, Pause, Play, RotateCcw, Square, Volume2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import { RevealText } from "@/components/assistant/reveal-text";
import { styleLabels } from "@/components/assistant/composer";
import { BrandMark } from "@/components/brand";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { ThinkingOrb } from "@/components/feedback/thinking-orb";
import { RecordAmount } from "@/components/records/record-bits";
import { Button } from "@/components/ui/button";
import type { Playback } from "@/hooks/use-speech";
import { displayLang, SPEECH_LIMITS, type DisplayStyle } from "@/lib/api/assistant";
import { formatMoney } from "@/lib/api/money";
import { recordOutcome } from "@/lib/api/privacy";
import type { Turn } from "@/lib/conversation";
import { answerCopy, answerDate, answerPeriod } from "@/lib/answer-copy";
import { kindLabels } from "@/lib/labels";

/** FinBoy's side of the conversation: the orb while it works, its mark once it has answered. */
function Avatar({ thinking }: { thinking: boolean }) {
  return (
    <span className="grid size-9 shrink-0 place-items-center rounded-full bg-white shadow-hairline" aria-hidden="true">
      {thinking ? <ThinkingOrb state="searching" size={20} /> : <BrandMark className="size-6" />}
    </span>
  );
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  useEffect(() => {
    if (!copied) return;
    const timer = window.setTimeout(() => setCopied(false), 1600);
    return () => window.clearTimeout(timer);
  }, [copied]);
  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label={copied ? "Copied" : "Copy answer"}
      className="size-9 text-ink-soft hover:text-ink"
      onClick={() => {
        void navigator.clipboard?.writeText(text).then(() => setCopied(true), () => undefined);
      }}
    >
      {copied ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
    </Button>
  );
}

/** "Thinking…", then an honest note once it is taking a while. */
function Thinking({ askedAt, onCancel }: { askedAt: number; onCancel: () => void }) {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    const timer = window.setTimeout(() => setSlow(true), Math.max(0, 4_000 - (Date.now() - askedAt)));
    return () => window.clearTimeout(timer);
  }, [askedAt]);
  return (
    <div className="flex min-h-9 flex-wrap items-center gap-x-3 gap-y-1 text-[15px]">
      <span className="shimmer-text font-medium">
        {slow ? "Checking your records… this can take up to a minute." : "Thinking…"}
      </span>
      <Button size="sm" variant="ghost" className="h-8 px-3" onClick={onCancel}>
        Cancel
      </Button>
    </div>
  );
}

/** One exchange: your question as a bubble, FinBoy's answer beside its mark. */
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
  // Reveal word by word only an answer that arrives while you watch, not one you come back to.
  const [sawPending, setSawPending] = useState(turn.state === "pending");
  if (turn.state === "pending" && !sawPending) setSawPending(true);
  const animate = sawPending && turn.state === "answered";
  const mine = playback.turnId === turn.id;
  const lang = answer ? displayLang(answer) : undefined;
  const copy = answerCopy(answer ?? { display_language: "en", display_script: "Latn" });
  return (
    <article aria-label={`Question: ${turn.question}`} className="space-y-4 motion-safe:animate-[rise-in_0.6s_var(--ease-out-expo)_both]">
      <div className="flex justify-end pl-10">
        <p className="surface max-w-[85%] rounded-[20px] rounded-br-md px-4 py-2.5 text-[15px] leading-relaxed break-words whitespace-pre-line">
          {turn.question}
        </p>
      </div>

      <div className="flex gap-3">
        <Avatar thinking={turn.state === "pending"} />
        <div className="min-w-0 flex-1 pt-1.5">
          {turn.state === "pending" && <Thinking askedAt={turn.askedAt} onCancel={onCancel} />}
          {turn.state === "cancelled" && (
            <div className="flex flex-wrap items-center gap-3 text-sm text-ink-soft">
              <span>You cancelled this question. Nothing was saved.</span>
              <Button size="sm" variant="outline" disabled={busy} onClick={onRetry}>
                <RotateCcw aria-hidden="true" /> Ask it again
              </Button>
            </div>
          )}
          {turn.state === "failed" && turn.problem && (
            <ProblemNotice problem={turn.problem} onRetry={busy ? undefined : onRetry} retryLabel="Ask again" />
          )}

          {answer && turn.state === "answered" && (
            <div className="space-y-4" lang={lang}>
              <div className="flex flex-wrap items-center gap-2 text-xs font-semibold">
                <span className="rounded-full bg-ink/[0.07] px-2.5 py-1 text-ink">{copy[answer.policy]}</span>
                {answer.resolved_period && (
                  // The API's period label is an ISO range; show the product's one date style instead.
                  <span className="rounded-full bg-muted px-2.5 py-1 text-ink-soft">
                    {answerPeriod(answer.resolved_period.start, answer.resolved_period.end, copy.locale)}
                  </span>
                )}
              </div>
              <RevealText text={answer.display_text} animate={animate} lang={lang} className="text-[17px] leading-relaxed text-ink" />
              {answer.facts.length > 0 && (
                <dl className="grid gap-2 sm:grid-cols-2" lang={lang}>
                  {answer.facts.map((fact, index) => (
                    <div
                      key={fact.key}
                      className="rounded-2xl bg-white/60 px-4 py-3 ring-1 ring-ink/5 motion-safe:animate-[rise-in_0.7s_var(--ease-out-expo)_both]"
                      style={{ animationDelay: animate ? `${500 + index * 90}ms` : "0ms" }}
                    >
                      <dt className="text-xs text-ink-soft">{fact.label}</dt>
                      <dd className="mt-0.5 text-lg font-semibold tabular-nums">
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
                <details className="group rounded-2xl bg-white/45 ring-1 ring-ink/5">
                  <summary className="flex min-h-11 cursor-pointer list-none items-center justify-between gap-3 rounded-2xl px-4 py-2.5 [&::-webkit-details-marker]:hidden">
                    <h3 className="text-sm font-semibold">
                      {copy.evidence}
                      <span className="font-normal text-ink-soft">
                        {answer.evidence_sampled
                          ? ` · ${copy.showing} ${answer.evidence_transactions.length} ${copy.of} ${answer.evidence_total} — ${copy.sample}`
                          : ` · ${copy.all} ${answer.evidence_transactions.length}`}
                      </span>
                    </h3>
                    <ChevronDown className="size-4 shrink-0 transition-transform duration-300 group-open:rotate-180" aria-hidden="true" />
                  </summary>
                  <ul className="divide-y border-t">
                    {answer.evidence_transactions.map((tx) => (
                      <li key={tx.id}>
                        <Link
                          href={`/transactions?selected=${tx.id}`}
                          onClick={() => recordOutcome("evidence_opened", tx.id)}
                          className="flex items-center justify-between gap-3 px-4 py-3 text-sm hover:bg-white/60"
                        >
                          <span className="min-w-0">
                            <span className="block font-semibold break-words text-ink underline underline-offset-4">{tx.merchant}</span>
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
                </details>
              )}

              <div className="-ml-2 flex flex-wrap items-center gap-1">
                {answer.speech_text.length > SPEECH_LIMITS.characters ? (
                  <p className="px-2 text-xs text-ink-soft">{copy.tooLong}</p>
                ) : mine && playback.step === "preparing" ? (
                  <>
                    <Button variant="ghost" size="sm" className="h-9" disabled>
                      <ThinkingOrb state="composing" size={20} /> {copy.preparing}
                    </Button>
                    <Button variant="ghost" size="sm" className="h-9" onClick={onStop}>
                      {copy.cancel}
                    </Button>
                  </>
                ) : mine && playback.step === "playing" ? (
                  <Button variant="ghost" size="sm" className="h-9" onClick={onStop}>
                    <Square aria-hidden="true" /> {copy.stop}
                  </Button>
                ) : mine && playback.step === "ready" ? (
                  <Button size="sm" className="h-9" onClick={onResume}>
                    <Play aria-hidden="true" /> {copy.ready}
                  </Button>
                ) : (
                  <Button variant="ghost" size="sm" className="h-9 text-ink-soft hover:text-ink" onClick={onPlay}>
                    <Volume2 aria-hidden="true" /> {mine && playback.step === "failed" ? copy.retry : copy.play}
                  </Button>
                )}
                <CopyButton text={answer.display_text} />
                {turn.style !== currentStyle && (
                  <Button variant="ghost" size="sm" className="h-9 text-ink-soft hover:text-ink" disabled={busy} onClick={onAskAgain}>
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
        </div>
      </div>
    </article>
  );
}
