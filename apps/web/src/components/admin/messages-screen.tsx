"use client";

import {
  Bell,
  FileText,
  Image as ImageIcon,
  LoaderCircle,
  type LucideIcon,
  Mic,
  MousePointerClick,
  Play,
  Reply,
  Volume2,
} from "lucide-react";
import Image from "next/image";
import { useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { count, day, RefreshButton } from "@/components/admin/admin-bits";
import { PageHeader } from "@/components/app-shell/page-header";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { LoadingPanel, RefreshingLabel } from "@/components/feedback/states";
import { Bubble } from "@/components/marketing/chat/bubbles";
import { Button } from "@/components/ui/button";
import { useResource } from "@/hooks/use-resource";
import { label, languageLabels, messageKindLabels, messageStatusLabels, readable } from "@/lib/admin-labels";
import { getHousehold, getMessageMedia, getMessages, type MessageRow } from "@/lib/api/admin";
import { formatDay, formatTime } from "@/lib/dates";
import { describeProblem } from "@/lib/messages";

const kb = (bytes: number) => `${Math.max(1, Math.round(bytes / 1024)).toLocaleString("en-IN")} KB`;
const KIND_ICONS: Partial<Record<MessageRow["kind"], LucideIcon>> = {
  voice: Mic,
  photo: ImageIcon,
  voice_reply: Volume2,
  tap: MousePointerClick,
  template: Bell,
};

/** Loads a kept voice note or photo only when asked, and lets the browser forget it afterwards. */
function useMediaUrl(messageId: string) {
  const [state, setState] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const current = useRef<string | null>(null);
  useEffect(
    () => () => {
      if (current.current) URL.revokeObjectURL(current.current);
    },
    [],
  );
  const load = async () => {
    setState("loading");
    try {
      const next = URL.createObjectURL(await getMessageMedia(messageId));
      current.current = next;
      setUrl(next);
      setState("ready");
    } catch (reason) {
      setError(reason);
      setState("error");
    }
  };
  return { state, url, error, load };
}

function MediaFile({ message }: { message: MessageRow }) {
  const media = useMediaUrl(message.id);
  const voice = message.media === "audio";
  const size = message.media_bytes ? ` · ${kb(message.media_bytes)}` : "";
  if (media.state === "ready" && media.url) {
    return voice ? (
      <audio controls autoPlay src={media.url} className="mt-1 h-10 w-64 max-w-full" aria-label="Voice note" />
    ) : (
      // A private blob URL: shown as fetched at its own shape, never sent to an image optimiser.
      <Image
        src={media.url}
        alt="Photo the household sent"
        width={320}
        height={320}
        unoptimized
        className="mt-1 h-auto max-h-80 w-auto max-w-full rounded-md"
      />
    );
  }
  return (
    <div className="mt-1 space-y-1">
      <Button type="button" variant="outline" size="sm" onClick={media.load} disabled={media.state === "loading"}>
        {media.state === "loading" ? (
          <LoaderCircle aria-hidden="true" className="animate-spin motion-reduce:animate-none" />
        ) : voice ? (
          <Play aria-hidden="true" />
        ) : (
          <ImageIcon aria-hidden="true" />
        )}
        {voice ? `Play voice note${size}` : `Show photo${size}`}
      </Button>
      {media.state === "error" && (
        <p role="alert" className="text-xs text-destructive">
          {describeProblem(media.error, "Couldn't open this file").title}
        </p>
      )}
    </div>
  );
}

function KindLine({ message }: { message: MessageRow }) {
  if (message.kind === "text" || message.kind === "buttons" || message.kind === "list") return null;
  const Icon = KIND_ICONS[message.kind] ?? FileText;
  return (
    <p className="flex items-center gap-1 text-[13px] font-semibold text-wa-meta">
      <Icon aria-hidden="true" className="size-3.5" />
      {label(messageKindLabels, message.kind)}
      {message.kind === "tap" && message.choices[0] ? `: ${readable(message.choices[0])}` : null}
    </p>
  );
}

function Message({ message, tail }: { message: MessageRow; tail: boolean }) {
  const finboy = message.direction === "out";
  const offered = finboy && message.choices.length > 0;
  return (
    <li className="flex">
      <Bubble from={finboy ? "finboy" : "you"} tail={tail} className="min-w-28 px-2 pt-1.5 pb-1">
        <span className="sr-only">{finboy ? "FinBoy: " : "Household: "}</span>
        <KindLine message={message} />
        {message.text && <p className="break-words whitespace-pre-wrap">{message.text}</p>}
        {message.media && <MediaFile message={message} />}
        {message.transcript !== null && (
          <p className="mt-1 text-[13px] break-words text-wa-meta">
            <span className="font-semibold">Heard{message.language ? ` (${label(languageLabels, message.language)})` : ""}: </span>
            {message.transcript || "nothing"}
          </p>
        )}
        {offered && (
          <ul aria-label={message.kind === "list" ? "List choices offered" : "Buttons offered"} className="mt-1 border-t border-black/10">
            {message.choices.map((choice) => (
              <li key={choice} className="flex items-center justify-center gap-1.5 py-1.5 text-[14px] font-medium text-wa-button">
                <Reply aria-hidden="true" className="size-4" />
                {choice}
              </li>
            ))}
          </ul>
        )}
        <p className="mt-0.5 flex flex-wrap items-center justify-end gap-x-1.5 text-[11px] leading-4 text-wa-meta">
          {message.channel === "web" && <span className="font-semibold">Ask on the web ·</span>}
          <time dateTime={message.at}>{formatTime(message.at)}</time>
          {finboy && message.status && <span>· {label(messageStatusLabels, message.status)}</span>}
          {!finboy && message.outcome && <span className="font-semibold text-destructive">· {readable(message.outcome)}</span>}
        </p>
      </Bubble>
    </li>
  );
}

/** Oldest first, one section per IST day, as WhatsApp shows a chat. */
function Days({ messages }: { messages: MessageRow[] }) {
  const days: { label: string; items: MessageRow[] }[] = [];
  for (const message of messages) {
    const label = formatDay(message.at);
    const last = days.at(-1);
    if (last?.label === label) last.items.push(message);
    else days.push({ label, items: [message] });
  }
  return (
    <div className="wa-wallpaper space-y-4 rounded-lg px-3 py-4 sm:px-6">
      {days.map((group) => (
        <section key={group.label} aria-label={group.label}>
          <h3 className="mx-auto mb-2 w-fit rounded-md bg-wa-bar px-2.5 py-1 text-xs font-medium text-wa-meta shadow-sm">
            {group.label}
          </h3>
          <ol className="space-y-1">
            {group.items.map((message, index) => (
              <Message
                key={message.id}
                message={message}
                tail={index === 0 || group.items[index - 1]?.direction !== message.direction}
              />
            ))}
          </ol>
        </section>
      ))}
    </div>
  );
}

/**
 * One household's kept messages (docs/conversation-round/contract.md): what it and FinBoy said on
 * WhatsApp and in Ask on the web, with voice notes and photos opened on request. Only households
 * that agreed have any; opening this page and each file is recorded in the audit log.
 */
export function MessagesScreen() {
  const params = useSearchParams();
  const householdId = params.get("household") ?? "";
  const household = useResource(`admin-household:${householdId}:messages`, (signal) => getHousehold(householdId, signal));
  const first = useResource(`admin-messages:${householdId}`, (signal) => getMessages(householdId, null, signal));
  const [earlier, setEarlier] = useState<{ key: string; items: MessageRow[]; next: string | null }>({ key: "", items: [], next: null });
  const [loadingEarlier, setLoadingEarlier] = useState(false);
  const [earlierError, setEarlierError] = useState<unknown>(null);
  const page = first.data;
  // Earlier pages belong to the first page they continued; a reload starts again from the newest.
  const firstKey = page ? `${householdId}:${page.items[0]?.id ?? "none"}:${page.next_before ?? ""}` : "";
  const older = earlier.key === firstKey ? earlier : { key: firstKey, items: [], next: page?.next_before ?? null };
  const shown = page ? [...page.items, ...older.items].reverse() : [];

  const loadEarlier = async () => {
    if (!older.next) return;
    setLoadingEarlier(true);
    setEarlierError(null);
    try {
      const next = await getMessages(householdId, older.next);
      setEarlier({ key: firstKey, items: [...older.items, ...next.items], next: next.next_before });
    } catch (reason) {
      setEarlierError(reason);
    } finally {
      setLoadingEarlier(false);
    }
  };

  const name = household.data?.name ?? (household.data ? "No name yet" : "Household");
  return (
    <div className="space-y-5">
      <PageHeader
        title="Messages"
        back={{ href: `/admin/households?selected=${householdId}`, label: "Back to the household" }}
        description={
          <>
            {name}
            {page?.kept_from ? ` · kept since ${day(page.kept_from)}` : null}
            {page ? ` · ${count(shown.length)} shown` : null}
          </>
        }
        actions={<RefreshButton resource={first} />}
      />
      <RefreshingLabel active={first.status === "refreshing"}>Updating…</RefreshingLabel>
      {first.status === "loading" && <LoadingPanel label="Loading messages…" />}
      {first.error !== null && (
        <ProblemNotice
          problem={describeProblem(first.error, page ? "Couldn't refresh — showing the last loaded messages" : "These messages couldn't be loaded")}
          onRetry={first.reload}
        />
      )}
      {page && shown.length === 0 && (
        <p className="surface rounded-lg px-4 py-6 text-center text-sm text-ink-soft">
          {page.kept_from
            ? "No messages kept yet."
            : page.declined_at
              ? `This household said No thanks to keeping its messages on ${day(page.declined_at)}, so none are kept.`
              : "This household hasn't agreed to keep its messages, so none are kept."}
        </p>
      )}
      {page && shown.length > 0 && (
        <section aria-labelledby="messages-title" className="space-y-3">
          <h2 id="messages-title" className="sr-only">
            Conversation, oldest first
          </h2>
          {older.next && (
            <div className="flex flex-col items-center gap-1">
              <Button type="button" variant="outline" size="sm" onClick={loadEarlier} disabled={loadingEarlier}>
                {loadingEarlier && <LoaderCircle aria-hidden="true" className="animate-spin motion-reduce:animate-none" />}
                Load earlier messages
              </Button>
              {earlierError !== null && (
                <p role="alert" className="text-xs text-destructive">
                  {describeProblem(earlierError, "Couldn't load earlier messages").title}
                </p>
              )}
            </div>
          )}
          <Days messages={shown} />
          <p className="text-center text-xs text-ink-soft">
            Household messages are on the right, FinBoy&apos;s on the left. Card, account and phone numbers, UPI IDs and
            login codes are masked when kept.
          </p>
        </section>
      )}
    </div>
  );
}
