"use client";
import Link from "next/link";
import { Mic, Send, Square, Volume2, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { SceneSlot } from "@/components/three/scene-slot";
import { styles, type DisplayStyle, type Answer } from "@/lib/api/assistant";
import { formatMoney, label, recordsNote } from "@/lib/api/money";

const styleLabels: Record<DisplayStyle, string> = {
  auto: "Match my question",
  en: "English",
  hi: "हिन्दी",
  hinglish: "Hinglish",
  ml: "മലയാളം",
  manglish: "Manglish",
};
type Props = {
  question: string;
  onQuestion: (text: string) => void;
  style: DisplayStyle;
  onStyle: (style: DisplayStyle) => void;
  answer: Answer | null;
  error: string | null;
  busy: boolean;
  transcribing: boolean;
  speaking: boolean;
  audioUrl: string | null;
  notice: string | null;
  voiceError: string | null;
  recording: boolean;
  requestingMic: boolean;
  recorderError: string | null;
  onRecord: () => void;
  onStop: () => void;
  onAsk: () => void;
  onListen: () => void;
};
export function AssistantScreen(props: Props) {
  const { answer, busy, recording, transcribing } = props;
  return (
    <div className="space-y-6">
      <header>
        <p className="eyebrow text-violet">A conversation with your records</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">
          Ask it your way.
        </h1>
        <p className="mt-3 max-w-xl text-sm leading-relaxed text-ink-soft">
          English, हिन्दी, മലയാളം — or the way you mix them. Every financial
          answer comes from your tracked ledger.
        </p>
      </header>
      <section className="surface relative overflow-hidden rounded-[2rem] p-5 sm:p-8">
        <div className="pointer-events-none absolute top-0 right-0 hidden h-48 w-48 opacity-60 xl:block">
          <SceneSlot
            spec={{
              name: "voice-orb",
              state: recording
                ? "listening"
                : busy || transcribing
                  ? "thinking"
                  : "idle",
            }}
            className="size-full"
          />
        </div>
        <div className="relative z-20 max-w-2xl">
          <p className="flex items-center gap-2 text-sm font-medium text-violet">
            <Sparkles className="size-4" /> Your numbers. In your language.
          </p>
          <form
            className="mt-6"
            onSubmit={(event) => {
              event.preventDefault();
              props.onAsk();
            }}
          >
            <label htmlFor="assistant-question" className="text-sm font-medium">
              Your question
            </label>
            <textarea
              id="assistant-question"
              value={props.question}
              onChange={(event) => props.onQuestion(event.target.value)}
              maxLength={2000}
              rows={3}
              placeholder="How much did I spend on food this month?"
              className="mt-3 block w-full resize-y rounded-2xl border bg-canvas/70 p-4 text-base leading-relaxed"
              required
              disabled={recording || transcribing}
            />
            <div className="mt-4 flex flex-wrap items-end gap-3">
              <label className="min-w-0 flex-1 text-xs font-medium">
                Reply style
                <select
                  value={props.style}
                  onChange={(event) => {
                    const result = styles.find(
                      (style) => style === event.target.value,
                    );
                    if (result) props.onStyle(result);
                  }}
                  className="mt-2 block h-11 w-full rounded-xl border bg-white px-3 text-sm"
                >
                  {styles.map((style) => (
                    <option key={style} value={style}>
                      {styleLabels[style]}
                    </option>
                  ))}
                </select>
              </label>
              <Button
                type="button"
                variant="outline"
                className="h-11"
                disabled={props.requestingMic || busy || transcribing}
                onClick={recording ? props.onStop : props.onRecord}
              >
                {recording ? (
                  <Square className="size-4" />
                ) : (
                  <Mic className="size-4" />
                )}
                {recording
                  ? "Stop recording"
                  : props.requestingMic
                    ? "Waiting for permission…"
                    : "Record question"}
              </Button>
              <Button
                className="h-11"
                type="submit"
                disabled={
                  busy ||
                  transcribing ||
                  recording ||
                  props.requestingMic ||
                  !props.question.trim()
                }
              >
                <Send className="size-4" />
                {busy ? "Checking records…" : "Ask FinBoy"}
              </Button>
            </div>
          </form>
          <p role="status" className="mt-4 text-xs text-ink-soft">
            {recording
              ? "Recording · stops before 30 seconds. Review the transcript before sending."
              : transcribing
                ? "Transcribing your recording…"
                : (props.notice ??
                  "Record up to 30 seconds, or type. FinBoy does not save your recording or question.")}
          </p>
        </div>
      </section>
      {[props.error, props.recorderError, props.voiceError]
        .filter(Boolean)
        .map((message) => (
          <p
            key={message}
            role="alert"
            className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-950"
          >
            {message}
          </p>
        ))}
      {!answer && !busy && (
        <div className="flex flex-wrap gap-2">
          {[
            "How much did I spend on food this month?",
            "इस महीने कितना पैसा बाकी है?",
            "ഈ മാസം ഭക്ഷണത്തിന് എത്ര ചെലവായി?",
            "Can I set aside ₹5,000 each month?",
          ].map((question) => (
            <button
              key={question}
              onClick={() => props.onQuestion(question)}
              className="rounded-2xl border bg-white/70 px-4 py-3 text-left text-xs leading-relaxed text-ink-soft hover:bg-lilac"
            >
              {question}
            </button>
          ))}
        </div>
      )}
      {busy && (
        <div role="status" className="surface rounded-3xl p-7">
          Checking your tracked records…
        </div>
      )}
      {answer && (
        <section
          className="surface rounded-3xl p-6 sm:p-8"
          aria-label="FinBoy answer"
        >
          <div className="flex flex-wrap items-center justify-between gap-4">
            <p className="eyebrow text-violet">
              {answer.policy === "decline"
                ? "A clear boundary"
                : answer.policy === "clarify"
                  ? "One more detail"
                  : "From your ledger"}
            </p>
            <Button
              variant="outline"
              disabled={props.speaking || answer.speech_text.length > 600}
              onClick={props.onListen}
            >
              <Volume2 className="size-4" />
              {props.speaking ? "Preparing audio…" : "Listen to answer"}
            </Button>
          </div>
          <p
            lang={answer.speech_language}
            className="mt-6 whitespace-pre-line text-lg leading-loose text-ink"
          >
            {answer.display_text}
          </p>
          {props.audioUrl && (
            <audio
              controls
              src={props.audioUrl}
              className="mt-5 w-full"
              onError={(event) => {
                event.currentTarget.setAttribute(
                  "aria-label",
                  "Audio playback failed. The text answer remains available.",
                );
              }}
              aria-label="Spoken FinBoy answer"
            />
          )}
          {answer.speech_text.length > 600 && (
            <p className="mt-4 text-xs text-ink-soft">
              This answer is too long for one audio response. The full text is
              above.
            </p>
          )}
          {answer.facts.length > 0 && (
            <dl className="mt-6 grid gap-3 sm:grid-cols-2">
              {answer.facts.map((fact) => (
                <div key={fact.key} className="rounded-2xl bg-canvas p-4">
                  <dt className="text-xs text-ink-soft">{label(fact.key)}</dt>
                  <dd className="mt-2 text-lg font-semibold">
                    {fact.amount_minor !== null
                      ? formatMoney(fact.amount_minor)
                      : (fact.count ?? "Unavailable")}
                  </dd>
                </div>
              ))}
            </dl>
          )}
          {answer.evidence_transactions.length > 0 && (
            <details className="mt-6 rounded-2xl border p-4">
              <summary className="cursor-pointer text-sm font-semibold">
                View supporting records ({answer.evidence_transactions.length})
              </summary>
              <ul className="mt-4 space-y-3">
                {answer.evidence_transactions.map((tx) => (
                  <li
                    key={tx.id}
                    className="flex justify-between gap-3 text-sm"
                  >
                    <Link
                      href="/transactions"
                      className="break-words text-violet underline"
                    >
                      {tx.merchant}
                    </Link>
                    <span className="shrink-0">
                      {formatMoney(tx.amount_minor)}
                    </span>
                  </li>
                ))}
              </ul>
            </details>
          )}
          {answer.warnings.length > 0 && (
            <ul className="mt-5 space-y-1 text-xs text-ink-soft">
              {answer.warnings.map((value) => (
                <li key={value}>{label(value)}</li>
              ))}
            </ul>
          )}
        </section>
      )}
      <p className="max-w-xl text-xs leading-relaxed text-ink-soft">
        {recordsNote} FinBoy can model cash flow; it does not pick funds or
        stocks.
      </p>
    </div>
  );
}
