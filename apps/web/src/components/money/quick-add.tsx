"use client";

import { Check, Mic, Plus, RotateCcw, Square } from "lucide-react";
import Link from "next/link";
import { useId, useState } from "react";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { ThinkingOrb } from "@/components/feedback/thinking-orb";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Textarea } from "@/components/ui/textarea";
import { useAction } from "@/hooks/use-action";
import { useMediaQuery } from "@/hooks/use-media-query";
import { useVoiceRecorder } from "@/hooks/use-voice-recorder";
import {
  type EntryFields,
  type EntryPreview,
  type EntrySaved,
  previewEntry,
  saveEntry,
} from "@/lib/api/entries";
import { categories, formatMoney, inputPaise, updateObligation } from "@/lib/api/money";
import { decide } from "@/lib/api/transactions";
import { istDate } from "@/lib/dates";
import { categoryLabels } from "@/lib/labels";

const EXAMPLES: { text: string; lang?: string }[] = [
  { text: "Paid the milkman 500" },
  { text: "Got salary 25,000" },
  { text: "School fees 2,000 due on the 10th" },
  { text: "दूधवाले को 500 दिए", lang: "hi" },
  { text: "പാൽക്കാരന് 500 കൊടുത്തു", lang: "ml" },
];

type Draft = {
  kind: EntryFields["kind"];
  amount: string;
  who: string;
  category: EntryFields["category"];
  date: string;
};

function draftFrom(preview: EntryPreview): Draft {
  const kind = preview.kind === "received" || preview.kind === "due" ? preview.kind : "spent";
  return {
    kind,
    amount: preview.amount_minor ? String(preview.amount_minor / 100) : "",
    who: (kind === "due" ? preview.label ?? preview.counterparty : preview.counterparty) ?? "",
    category: preview.category,
    date: (kind === "due" ? preview.due_date : preview.day) ?? istDate(new Date()),
  };
}

const kindNames: Record<Draft["kind"], string> = {
  spent: "Money out",
  received: "Money in",
  due: "To pay later",
};

/**
 * Quick add: say or type one sentence, check the card, Save. Save is the confirmation; Undo right
 * here rejects the entry (a due is dismissed) so it stops counting without waiting in Review. The
 * sentence itself is never stored.
 */
export function QuickAdd({
  open,
  onOpenChange,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}) {
  const ids = useId();
  const wide = useMediaQuery("(min-width: 640px)");
  const action = useAction();
  const [text, setText] = useState("");
  const [hint, setHint] = useState<"question" | "unclear" | null>(null);
  const [draft, setDraft] = useState<Draft | null>(null);
  const [saved, setSaved] = useState<{ result: EntrySaved; summary: string } | null>(null);
  const [undone, setUndone] = useState(false);
  const voice = useVoiceRecorder((transcript) => setText(transcript));
  const listening = voice.state.step === "requesting" || voice.state.step === "recording";
  const amount = draft ? inputPaise(draft.amount) : null;
  const today = istDate(new Date());

  function reset() {
    setText("");
    setHint(null);
    setDraft(null);
    setSaved(null);
    setUndone(false);
    action.clear();
    voice.reset();
  }

  async function read() {
    const sentence = text.trim();
    if (!sentence) return;
    setHint(null);
    const preview = await action.run("read", "FinBoy couldn't read that", () => previewEntry(sentence));
    if (!preview) return;
    if (preview.kind === "question" || preview.kind === "unclear" || !preview.amount_minor) {
      setHint(preview.kind === "question" ? "question" : "unclear");
      return;
    }
    setDraft(draftFrom(preview));
  }

  async function save() {
    if (!draft || amount === null) return;
    const result = await action.run("save", "This entry wasn't saved", () =>
      saveEntry({
        kind: draft.kind,
        amount_minor: amount,
        counterparty: draft.who.trim() || null,
        label: draft.who.trim() || null,
        category: draft.category,
        day: draft.kind === "due" ? null : draft.date,
        due_date: draft.kind === "due" ? draft.date : null,
      }),
    );
    if (!result) return;
    setSaved({
      result,
      summary: `${formatMoney(amount)} · ${draft.who.trim() || kindNames[draft.kind]}`,
    });
    onSaved();
  }

  async function undo() {
    if (!saved) return;
    const { result } = saved;
    const ok = await action.run("undo", "This entry couldn't be undone", async () => {
      if (result.kind === "record" && result.transaction_id) {
        // Undoing the Save itself would only send the entry back to Review.
        await decide(result.transaction_id, { action: "reject", expected_version: result.data_version });
      } else if (result.obligation_id) {
        await updateObligation(result.obligation_id, {
          expected_version: result.data_version,
          status: "dismissed",
        });
      }
      return true;
    });
    if (ok) {
      setUndone(true);
      onSaved();
    }
  }

  const dateInvalid =
    draft !== null &&
    (draft.kind === "due" ? draft.date < today : draft.date > today || !draft.date);

  return (
    <Sheet
      open={open}
      onOpenChange={(next) => {
        onOpenChange(next);
        if (!next) reset();
      }}
    >
      <SheetContent
        side={wide ? "right" : "bottom"}
        className="max-h-[92dvh] gap-0 overflow-y-auto p-5 sm:max-w-md sm:p-6"
        aria-describedby={`${ids}-description`}
      >
        <SheetHeader className="p-0">
          <SheetTitle className="text-xl">Add money in or out</SheetTitle>
          <SheetDescription id={`${ids}-description`}>
            Say or type it the way you&apos;d tell a friend. Nothing is added until you save.
          </SheetDescription>
        </SheetHeader>

        {saved ? (
          <div className="mt-5 space-y-4" role="status">
            <p className="flex items-center gap-3 rounded-2xl bg-sunflower/50 p-4 text-base font-semibold">
              <Check className="size-5 shrink-0" aria-hidden="true" />
              {undone ? `Undone: ${saved.summary}` : `Added: ${saved.summary}`}
            </p>
            {action.problem && <ProblemNotice problem={action.problem} />}
            <div className="flex flex-wrap gap-2">
              {!undone && (
                <Button variant="outline" onClick={() => void undo()} disabled={action.busy !== null}>
                  <RotateCcw aria-hidden="true" /> {action.busy === "undo" ? "Undoing…" : "Undo"}
                </Button>
              )}
              <Button onClick={reset}>
                <Plus aria-hidden="true" /> Add another
              </Button>
              <Button variant="ghost" onClick={() => onOpenChange(false)}>
                Done
              </Button>
            </div>
          </div>
        ) : draft ? (
          <form
            className="mt-5 space-y-4"
            onSubmit={(event) => {
              event.preventDefault();
              void save();
            }}
          >
            <fieldset>
              <legend className="text-sm font-semibold">What is it?</legend>
              <div className="mt-2 grid grid-cols-3 gap-2">
                {(Object.keys(kindNames) as Draft["kind"][]).map((kind) => (
                  <label
                    key={kind}
                    className="flex min-h-11 cursor-pointer items-center justify-center rounded-full border px-2 text-center text-xs font-semibold has-checked:border-ink has-checked:bg-ink has-checked:text-white"
                  >
                    <input
                      type="radio"
                      name={`${ids}-kind`}
                      className="sr-only"
                      checked={draft.kind === kind}
                      onChange={() =>
                        setDraft({
                          ...draft,
                          kind,
                          date: kind === "due" && draft.date < today ? today : kind !== "due" && draft.date > today ? today : draft.date,
                        })
                      }
                    />
                    {kindNames[kind]}
                  </label>
                ))}
              </div>
            </fieldset>
            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <label htmlFor={`${ids}-amount`} className="text-sm font-semibold">
                  Amount (₹)
                </label>
                <Input
                  id={`${ids}-amount`}
                  inputMode="decimal"
                  autoComplete="off"
                  value={draft.amount}
                  aria-invalid={amount === null || undefined}
                  onChange={(event) => setDraft({ ...draft, amount: event.target.value })}
                />
              </div>
              <div className="space-y-1.5">
                <label htmlFor={`${ids}-date`} className="text-sm font-semibold">
                  {draft.kind === "due" ? "Due on" : "Date"}
                </label>
                <Input
                  id={`${ids}-date`}
                  type="date"
                  value={draft.date}
                  min={draft.kind === "due" ? today : undefined}
                  max={draft.kind === "due" ? undefined : today}
                  aria-invalid={dateInvalid || undefined}
                  onChange={(event) => setDraft({ ...draft, date: event.target.value })}
                />
              </div>
            </div>
            <div className="space-y-1.5">
              <label htmlFor={`${ids}-who`} className="text-sm font-semibold">
                {draft.kind === "due" ? "What it's for" : draft.kind === "received" ? "From" : "To or for"}{" "}
                <span className="font-normal text-ink-soft">(optional)</span>
              </label>
              <Input
                id={`${ids}-who`}
                maxLength={60}
                value={draft.who}
                onChange={(event) => setDraft({ ...draft, who: event.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <label htmlFor={`${ids}-category`} className="text-sm font-semibold">
                Category
              </label>
              <select
                id={`${ids}-category`}
                value={draft.category}
                onChange={(event) =>
                  setDraft({ ...draft, category: event.target.value as Draft["category"] })
                }
                className="h-11 w-full rounded-2xl border border-input bg-white/80 px-3 text-sm"
              >
                {categories.map((category) => (
                  <option key={category} value={category}>
                    {categoryLabels[category]}
                  </option>
                ))}
              </select>
            </div>
            {action.problem && <ProblemNotice problem={action.problem} />}
            <div className="flex flex-wrap gap-2">
              <Button type="submit" size="lg" disabled={action.busy !== null || amount === null || dateInvalid}>
                <Check aria-hidden="true" /> {action.busy === "save" ? "Saving…" : "Save"}
              </Button>
              <Button type="button" variant="ghost" onClick={() => setDraft(null)}>
                Back
              </Button>
            </div>
          </form>
        ) : (
          <form
            className="mt-5 space-y-3"
            onSubmit={(event) => {
              event.preventDefault();
              void read();
            }}
          >
            <label htmlFor={`${ids}-text`} className="sr-only">
              What happened?
            </label>
            <Textarea
              id={`${ids}-text`}
              rows={3}
              maxLength={500}
              placeholder="Paid the milkman 500"
              enterKeyHint="next"
              value={text}
              onChange={(event) => {
                setText(event.target.value);
                setHint(null);
              }}
              onKeyDown={(event) => {
                // One sentence, so Enter works like Next. Shift+Enter still breaks the line, and
                // Enter that picks a word in a Hindi input method (229 in Safari) is left alone.
                if (event.key !== "Enter" || event.shiftKey) return;
                if (event.nativeEvent.isComposing || event.keyCode === 229) return;
                event.preventDefault();
                if (text.trim() && action.busy === null && !listening) void read();
              }}
              className="rounded-2xl text-base"
            />
            <div className="flex flex-wrap gap-2">
              {EXAMPLES.map((example) => (
                <button
                  key={example.text}
                  type="button"
                  lang={example.lang}
                  className="rounded-full bg-well px-3 py-1.5 text-xs font-medium ring-1 ring-ink/5 hover:bg-white"
                  onClick={() => {
                    setText(example.text);
                    setHint(null);
                  }}
                >
                  {example.text}
                </button>
              ))}
            </div>
            {hint === "question" && (
              <p role="status" className="rounded-2xl bg-white/70 p-3 text-sm leading-relaxed">
                That sounds like a question.{" "}
                <Link href="/assistant" className="font-semibold underline underline-offset-4">
                  Ask FinBoy instead
                </Link>
                .
              </p>
            )}
            {hint === "unclear" && (
              <p role="status" className="rounded-2xl bg-white/70 p-3 text-sm leading-relaxed">
                Say it with an amount, like <strong>&ldquo;Spent 500 on milk&rdquo;</strong>,{" "}
                <strong>&ldquo;Got 2,000 from PM Kisan&rdquo;</strong> or{" "}
                <strong lang="ml">&ldquo;പാൽക്കാരന് 500 കൊടുത്തു&rdquo;</strong>.
              </p>
            )}
            {voice.state.step === "error" && <ProblemNotice problem={voice.state.problem} />}
            {action.problem && <ProblemNotice problem={action.problem} />}
            <div className="flex flex-wrap items-center gap-2">
              <Button type="submit" size="lg" disabled={!text.trim() || action.busy !== null || listening}>
                {action.busy === "read" ? "Reading…" : "Next"}
              </Button>
              {listening ? (
                <Button type="button" variant="outline" size="lg" onClick={voice.stop}>
                  <Square aria-hidden="true" /> Stop
                </Button>
              ) : (
                <Button
                  type="button"
                  variant="outline"
                  size="lg"
                  onClick={() => void voice.start()}
                  disabled={action.busy !== null || voice.state.step === "transcribing"}
                >
                  <Mic aria-hidden="true" /> {voice.state.step === "transcribing" ? "Listening…" : "Say it"}
                </Button>
              )}
              {(listening || voice.state.step === "transcribing" || action.busy === "read") && (
                <ThinkingOrb state={listening ? "listening" : "working"} size={20} />
              )}
            </div>
          </form>
        )}
      </SheetContent>
    </Sheet>
  );
}
