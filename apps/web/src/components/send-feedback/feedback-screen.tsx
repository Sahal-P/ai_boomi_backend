"use client";

import { Bug, Lightbulb, MessageSquareText, Send, Trash2, type LucideIcon } from "lucide-react";
import { useSearchParams } from "next/navigation";
import { useEffect, useId, useState } from "react";
import { PageHeader } from "@/components/app-shell/page-header";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { LoadingPanel } from "@/components/feedback/states";
import { ScreenshotPicker, type Attachment } from "@/components/send-feedback/screenshot-picker";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useResource } from "@/hooks/use-resource";
import {
  deleteFeedback,
  FEEDBACK_MESSAGE_LIMIT,
  listFeedback,
  screenFrom,
  sendFeedback,
  type FeedbackItem,
  type FeedbackKind,
  type FeedbackStatus,
} from "@/lib/api/feedback";
import { formatDayTime } from "@/lib/dates";
import { describeProblem, type Problem } from "@/lib/messages";
import { setUnsaved } from "@/lib/unsaved-work";

const KINDS: { kind: FeedbackKind; label: string; icon: LucideIcon; prompt: string; hint: string }[] = [
  {
    kind: "problem",
    label: "Problem",
    icon: Bug,
    prompt: "What went wrong?",
    hint: "What you did, what you expected, and what happened instead.",
  },
  {
    kind: "idea",
    label: "Idea",
    icon: Lightbulb,
    prompt: "What would make FinBoy better?",
    hint: "What you'd like FinBoy to do, and how it would help you.",
  },
  {
    kind: "other",
    label: "Other",
    icon: MessageSquareText,
    prompt: "Your message",
    hint: "Anything else you'd like the FinBoy team to know.",
  },
];
const kindLabel = (kind: FeedbackKind) => KINDS.find((item) => item.kind === kind)?.label ?? "Feedback";

const STATUSES: Record<FeedbackStatus, { label: string; variant: "default" | "warning" | "positive"; detail: string }> = {
  new: { label: "New", variant: "default", detail: "The team will look at it soon." },
  planned: { label: "Planned", variant: "warning", detail: "It's on the team's list." },
  done: { label: "Done", variant: "positive", detail: "Fixed or added." },
};

const SCREENS: Record<string, string> = {
  dashboard: "Home",
  transactions: "Transactions",
  review: "To review",
  reports: "Reports",
  assistant: "Ask",
  sources: "Sources",
  privacy: "Privacy & data",
  memory: "Memory",
  plan: "Plan",
  import: "Import",
  connect: "Connect",
};
const screenName = (path: string) => SCREENS[path.split("/")[1] ?? ""] ?? path;

/** One sent item with its status, and Delete. */
function FeedbackRow({ item, onDelete }: { item: FeedbackItem; onDelete: (item: FeedbackItem) => void }) {
  const status = STATUSES[item.status];
  const details = [
    status.detail,
    item.page ? `From ${screenName(item.page)}` : null,
    item.has_screenshot ? "Screenshot attached" : null,
  ].filter(Boolean);
  return (
    <li className="flex items-start gap-3 py-3">
      <div className="min-w-0 flex-1">
        <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <Badge variant={status.variant}>{status.label}</Badge>
          <span className="text-sm font-semibold">{kindLabel(item.kind)}</span>
          <span className="text-xs text-ink-soft">{formatDayTime(item.created_at)}</span>
        </p>
        <p className="mt-1.5 text-[15px] break-words whitespace-pre-wrap text-ink">{item.message}</p>
        <p className="mt-1 text-xs text-ink-soft">{details.join(" · ")}</p>
      </div>
      <Button
        variant="ghost"
        size="icon"
        className="size-11 shrink-0"
        aria-label={`Delete your ${kindLabel(item.kind).toLowerCase()} from ${formatDayTime(item.created_at)}`}
        onClick={() => onDelete(item)}
      >
        <Trash2 aria-hidden="true" />
      </Button>
    </li>
  );
}

/**
 * Feedback to the FinBoy team (docs/feedback-round/contract.md): a problem, an idea or anything
 * else, with the screen it came from and one optional screenshot, and the status of each item.
 */
export function FeedbackScreen() {
  const ids = useId();
  const from = screenFrom(useSearchParams().get("from"));
  const list = useResource("feedback", (signal) => listFeedback(signal));
  const [kind, setKind] = useState<FeedbackKind>("problem");
  const [message, setMessage] = useState("");
  const [attachment, setAttachment] = useState<Attachment | null>(null);
  const [sending, setSending] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [removing, setRemoving] = useState<FeedbackItem | null>(null);
  const chosen = KINDS.find((item) => item.kind === kind) ?? KINDS[0]!;
  const text = message.trim();
  const dirty = text !== "" || attachment !== null;
  const data = list.data;

  useEffect(() => {
    setUnsaved("feedback", dirty);
  }, [dirty]);
  useEffect(() => () => setUnsaved("feedback", false), []);

  async function send() {
    if (!text || sending) return;
    setSending(true);
    setProblem(null);
    setNotice(null);
    try {
      const sent = await sendFeedback({ kind, message: text, page: from, screenshot: attachment?.screenshot ?? null });
      if (data) list.replace({ ...data, items: [sent.item, ...data.items].slice(0, 50) });
      else list.reload();
      setNotice(
        attachment && !sent.screenshot_saved
          ? "Thank you. Your message reached the FinBoy team, but the screenshot couldn't be saved."
          : "Thank you. The FinBoy team has your feedback — you'll see its status below.",
      );
      setMessage("");
      setAttachment(null);
    } catch (error) {
      setProblem(describeProblem(error, "Your feedback wasn't sent"));
    } finally {
      setSending(false);
    }
  }

  async function remove(item: FeedbackItem) {
    setProblem(null);
    setNotice(null);
    try {
      await deleteFeedback(item.id);
      if (data) list.replace({ ...data, items: data.items.filter((row) => row.id !== item.id) });
      setNotice("Deleted. The FinBoy team won't see it any more.");
    } catch (error) {
      setProblem(describeProblem(error, "That feedback couldn't be deleted"));
    }
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Send feedback"
        description="Tell the FinBoy team what went wrong or what would make FinBoy better. Every message is read."
      />
      <div role="status" aria-live="polite">
        {notice && <p className="rounded-2xl bg-white/60 p-4 text-sm font-medium">{notice}</p>}
      </div>
      {problem && <ProblemNotice problem={problem} />}

      <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-[1.2fr_1fr]">
        <section aria-labelledby={`${ids}-form`} className="surface rounded-3xl p-5 sm:p-6">
          <h2 id={`${ids}-form`} className="sr-only">
            New feedback
          </h2>
          <form
            className="space-y-5"
            onSubmit={(event) => {
              event.preventDefault();
              void send();
            }}
          >
            <fieldset disabled={sending}>
              <legend className="text-sm font-semibold">What is it about?</legend>
              <div className="mt-2 grid grid-cols-3 gap-2">
                {KINDS.map(({ kind: value, label, icon: Icon }) => (
                  <label
                    key={value}
                    className="flex min-h-11 cursor-pointer items-center justify-center gap-1.5 rounded-full border px-2 text-center text-sm font-semibold has-checked:border-ink has-checked:bg-ink has-checked:text-white has-focus-visible:outline-2 has-focus-visible:outline-offset-2"
                  >
                    <input
                      type="radio"
                      name={`${ids}-kind`}
                      className="sr-only"
                      checked={kind === value}
                      onChange={() => setKind(value)}
                    />
                    <Icon className="size-4 shrink-0" aria-hidden="true" />
                    {label}
                  </label>
                ))}
              </div>
            </fieldset>

            <div className="space-y-1.5">
              <label htmlFor={`${ids}-message`} className="text-sm font-semibold">
                {chosen.prompt}
              </label>
              <p id={`${ids}-hint`} className="text-xs text-ink-soft">
                {chosen.hint} Please leave out card numbers, passwords and one-time codes.
              </p>
              <Textarea
                id={`${ids}-message`}
                value={message}
                maxLength={FEEDBACK_MESSAGE_LIMIT}
                disabled={sending}
                aria-describedby={`${ids}-hint ${ids}-count`}
                onChange={(event) => setMessage(event.target.value)}
                className="min-h-36"
              />
              <p id={`${ids}-count`} className="text-right text-xs text-ink-soft tabular-nums">
                {message.length.toLocaleString("en-IN")} / {FEEDBACK_MESSAGE_LIMIT.toLocaleString("en-IN")}
              </p>
            </div>

            {data?.screenshots && (
              <ScreenshotPicker value={attachment} onChange={setAttachment} disabled={sending} />
            )}

            <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
              <Button type="submit" disabled={!text || sending}>
                <Send aria-hidden="true" /> {sending ? "Sending…" : "Send feedback"}
              </Button>
              {from && <p className="text-xs text-ink-soft">The screen you came from, {screenName(from)}, is sent with it.</p>}
            </div>
          </form>
        </section>

        <section aria-labelledby={`${ids}-sent`} className="surface rounded-3xl p-5 sm:p-6">
          <h2 id={`${ids}-sent`} className="text-lg font-semibold">
            Your feedback
          </h2>
          <p className="mt-1 text-sm text-ink-soft">New, Planned or Done — each one shows where it stands.</p>
          {list.status === "loading" && <LoadingPanel label="Loading your feedback…" className="mt-4 p-4" />}
          {list.error !== null && (
            <ProblemNotice
              className="mt-4"
              problem={describeProblem(list.error, data ? "Couldn't refresh your feedback" : "Your feedback couldn't be loaded")}
              onRetry={list.reload}
            />
          )}
          {data &&
            (data.items.length === 0 ? (
              <p className="mt-4 text-sm text-ink-soft">Nothing sent yet. What you send shows here with its status.</p>
            ) : (
              <ul aria-label="Feedback you sent" className="mt-2 divide-y">
                {data.items.map((item) => (
                  <FeedbackRow key={item.id} item={item} onDelete={setRemoving} />
                ))}
              </ul>
            ))}
        </section>
      </div>

      <AlertDialog open={removing !== null} onOpenChange={(open) => !open && setRemoving(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this feedback?</AlertDialogTitle>
            <AlertDialogDescription>
              The FinBoy team won&apos;t see it any more, and its screenshot is deleted too. This can&apos;t be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => {
                const item = removing;
                setRemoving(null);
                if (item) void remove(item);
              }}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
