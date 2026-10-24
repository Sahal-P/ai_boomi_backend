"use client";

import { Send, Trash2 } from "lucide-react";
import { useId, useState } from "react";
import { PageHeader } from "@/components/app-shell/page-header";
import { styleLabels, TurnCard } from "@/components/assistant/turn-card";
import { VoiceControls } from "@/components/assistant/voice-controls";
import { Button } from "@/components/ui/button";
import { useAssistant } from "@/hooks/use-assistant";
import { useSpeech } from "@/hooks/use-speech";
import { useVoiceRecorder } from "@/hooks/use-voice-recorder";
import { styles } from "@/lib/api/assistant";
import { recordsNote } from "@/lib/api/money";

const examples = [
  { text: "How much did I spend on food this month?", lang: "en" },
  { text: "How much did I spend at Amazon last month?", lang: "en" },
  { text: "इस महीने कितना पैसा बाकी है?", lang: "hi" },
  { text: "ഈ മാസം ഭക്ഷണത്തിന് എത്ര ചെലവായി?", lang: "ml" },
  { text: "Can I set aside ₹5,000 each month?", lang: "en" },
];

export function AssistantScreen() {
  const assistant = useAssistant();
  const speech = useSpeech();
  const [draft, setDraft] = useState("");
  const [fromVoice, setFromVoice] = useState(false);
  const voice = useVoiceRecorder((transcript) => {
    setDraft(transcript);
    setFromVoice(true);
  });
  const ids = useId();
  const voiceBusy =
    voice.state.step === "requesting" ||
    voice.state.step === "recording" ||
    voice.state.step === "transcribing";

  function submit() {
    if (assistant.ask(draft)) {
      setDraft("");
      setFromVoice(false);
      voice.reset();
    }
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Ask FinBoy"
        description="Ask in English, हिन्दी or മലയാളം — or mix them. AI helps explain your money and plan purchases; financial totals use confirmed household records."
      />
      <section aria-labelledby={`${ids}-ask`} className="surface rounded-3xl p-5 sm:p-7">
        <h2 id={`${ids}-ask`} className="sr-only">
          Ask a question
        </h2>
        <details className="rounded-2xl bg-canvas px-4 py-3 text-sm">
          <summary className="cursor-pointer font-semibold">What can I ask?</summary>
          <ul className="mt-2 list-disc space-y-1 pl-5 leading-relaxed text-ink-soft">
            <li>Spending for today, yesterday, this month, last month or a month like 2026-09.</li>
            <li>Spending by category or at a merchant, including refunds.</li>
            <li>How much is left this month, and whether you can set aside a monthly amount.</li>
            <li>Planning a purchase: discuss the quote, savings and cash or financing options.</li>
            <li>FinBoy doesn&apos;t pick funds or stocks, and only counts confirmed records.</li>
          </ul>
        </details>
        <form
          className="mt-4"
          onSubmit={(event) => {
            event.preventDefault();
            submit();
          }}
        >
          <label htmlFor={`${ids}-question`} className="text-sm font-medium">
            {fromVoice ? "Your question (from your recording — check it)" : "Your question"}
          </label>
          <textarea
            id={`${ids}-question`}
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            maxLength={2000}
            rows={3}
            placeholder="How much did I spend on food this month?"
            className="mt-2 block w-full resize-y rounded-2xl border border-input bg-canvas/60 p-4 text-base leading-relaxed"
            disabled={voiceBusy}
          />
          <div className="mt-3 flex flex-wrap items-end gap-3">
            <div className="min-w-48 flex-1">
              <label htmlFor={`${ids}-style`} className="text-xs font-semibold">
                Reply style
              </label>
              <select
                id={`${ids}-style`}
                value={assistant.style}
                aria-describedby={`${ids}-style-hint`}
                onChange={(event) => {
                  const next = styles.find((style) => style === event.target.value);
                  if (next) assistant.setStyle(next);
                }}
                className="mt-1.5 block h-11 w-full rounded-xl border border-input bg-white px-3 text-sm"
              >
                {styles.map((style) => (
                  <option key={style} value={style} lang={styleLabels[style].lang}>
                    {styleLabels[style].label}
                  </option>
                ))}
              </select>
              <p id={`${ids}-style-hint`} className="mt-1 text-xs text-ink-soft">
                Applies to your next question; remembered for this browser session.
              </p>
            </div>
            <Button type="submit" disabled={assistant.pending || voiceBusy || !draft.trim()}>
              <Send aria-hidden="true" /> {assistant.pending ? "Waiting for the answer…" : "Ask"}
            </Button>
          </div>
        </form>
        <div className="mt-4 border-t pt-4">
          <VoiceControls
            state={voice.state}
            level={voice.level}
            disabled={assistant.pending}
            onStart={voice.start}
            onStop={voice.stop}
            onCancel={voice.cancel}
            onDiscardTranscript={() => {
              setDraft("");
              setFromVoice(false);
              voice.reset();
            }}
          />
        </div>
      </section>

      {!assistant.turns.length && (
        <section aria-label="Example questions">
          <h2 className="text-sm font-semibold">Try one of these</h2>
          <div className="mt-2 flex flex-wrap gap-2">
            {examples.map((example) => (
              <button
                key={example.text}
                type="button"
                lang={example.lang}
                onClick={() => setDraft(example.text)}
                className="min-h-11 rounded-2xl border bg-white/80 px-4 py-2.5 text-left text-sm leading-relaxed text-ink hover:bg-lilac"
              >
                {example.text}
              </button>
            ))}
          </div>
        </section>
      )}

      {assistant.turns.length > 0 && (
        <section aria-label="This session's questions" className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="text-sm font-semibold">This session</h2>
            <Button variant="ghost" size="sm" onClick={assistant.clear}>
              <Trash2 aria-hidden="true" /> Clear
            </Button>
          </div>
          {assistant.turns.map((turn) => (
            <TurnCard
              key={turn.id}
              turn={turn}
              currentStyle={assistant.style}
              playback={speech.playback}
              busy={assistant.pending}
              onPlay={() => {
                if (turn.answer) speech.play(turn.id, turn.answer);
              }}
              onResume={() => speech.resume(turn.id)}
              onStop={speech.stop}
              onRetry={() => assistant.retry(turn.id)}
              onCancel={assistant.cancel}
              onAskAgain={() => assistant.ask(turn.question)}
            />
          ))}
          <p className="text-xs text-ink-soft">
            Questions and answers stay on this page until you reload or clear them. FinBoy
            doesn&apos;t keep them.
          </p>
        </section>
      )}

      <p className="max-w-xl text-xs leading-relaxed text-ink-soft">
        {recordsNote} FinBoy can model cash flow; it doesn&apos;t pick funds or stocks.
      </p>
    </div>
  );
}
