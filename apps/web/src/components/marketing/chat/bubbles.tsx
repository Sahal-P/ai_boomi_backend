import {
  ArrowLeft,
  Camera,
  CheckCheck,
  EllipsisVertical,
  FaceSlightlySmiling,
  List,
  Mic,
  Paperclip,
  Phone,
  Reply,
  Video,
} from "lucide-react";
import { Fragment, type ReactNode, type Ref } from "react";

import { BrandMark } from "@/components/brand";
import { cn } from "@/lib/utils";

/**
 * WhatsApp for Android's chat parts, drawn in the wa-* tokens (globals.css): bubbles with tails,
 * times and grey "delivered" ticks (FinBoy sends no read receipts), reply buttons inside the
 * bubble under a hairline, and the bars above and below the chat.
 */

export const BUBBLE_SHADOW = "shadow-[0_1px_0.5px_rgb(11_20_26/0.13)]";
const FOCUS = "outline-none focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-wa-button";

/** A message line's leading emoji (or bullet), hidden from screen readers like any decoration. */
const LEAD = /^(\p{Extended_Pictographic}️?|•) (.+)$/u;

export function Line({ text }: { text: string }) {
  const lead = LEAD.exec(text);
  if (!lead) return <>{text}</>;
  return (
    <>
      <span aria-hidden="true">{lead[1]} </span>
      {lead[2]}
    </>
  );
}

/** FinBoy's text exactly as sent: one line per line, blank lines kept, room left for the time. */
export function MessageText({ text, sent = false }: { text: string; sent?: boolean }) {
  return (
    <>
      {text.split("\n").map((line, index) => (
        <Fragment key={index}>
          {index > 0 ? <br /> : null}
          <Line text={line} />
        </Fragment>
      ))}
      <Spacer sent={sent} />
    </>
  );
}

/** The bubble's tail at its top outer corner: an original shape in the bubble's own colour. */
function Tail({ side }: { side: "out" | "in" }) {
  return (
    <svg
      viewBox="0 0 8 13"
      aria-hidden="true"
      className={cn(
        "absolute -top-px h-[13px] w-2 forced-colors:hidden",
        side === "out" ? "-right-[9px] text-wa-out" : "-left-[9px] text-wa-in",
      )}
    >
      <path d={side === "out" ? "M0 0h8C5.2 2.4 2.6 6.6 0 13z" : "M8 0H0c2.8 2.4 5.4 6.6 8 13z"} fill="currentColor" />
    </svg>
  );
}

/**
 * A message bubble. Only the first of a run has a tail, as in WhatsApp. A transparent border still
 * outlines it in forced-colours mode.
 */
export function Bubble({
  from,
  tail,
  className,
  children,
}: {
  from: "you" | "finboy";
  tail: boolean;
  className?: string | undefined;
  children: ReactNode;
}) {
  const you = from === "you";
  return (
    <div
      data-from={from}
      className={cn(
        "relative w-fit max-w-[85%] rounded-[7.5px] border border-transparent text-[15px] leading-5 text-wa-text",
        BUBBLE_SHADOW,
        you ? "ml-auto bg-wa-out" : "mr-auto bg-wa-in",
        tail && (you ? "rounded-tr-none" : "rounded-tl-none"),
        className,
      )}
    >
      {tail ? <Tail side={you ? "out" : "in"} /> : null}
      {children}
    </div>
  );
}

/** Keeps room on the last line for the time, as WhatsApp does; the time drops a line if needed. */
export function Spacer({ sent = false }: { sent?: boolean }) {
  return <span aria-hidden="true" className={cn("inline-block h-3", sent ? "w-[4.5rem]" : "w-14")} />;
}

/** The time, and for your messages two grey ticks. */
export function Meta({ time, sent = false }: { time: string; sent?: boolean }) {
  return (
    <span
      aria-hidden="true"
      className="absolute right-2 bottom-1 inline-flex items-center gap-1 text-[11px] leading-4 whitespace-nowrap text-wa-meta"
    >
      {time}
      {sent ? <CheckCheck className="size-4" strokeWidth={2} /> : null}
    </span>
  );
}

/** Your reply quotes FinBoy's message, as WhatsApp shows a tapped button or list choice. */
export function Quote({ text }: { text: string }) {
  return (
    <span aria-hidden="true" className="mb-1 flex overflow-hidden rounded-[5px] bg-wa-quote">
      <span className="w-1 shrink-0 bg-wa-quote-name" />
      <span className="min-w-0 px-2 py-1">
        <span className="block text-[13px] font-semibold text-wa-quote-name">FinBoy</span>
        <span className="line-clamp-2 text-[13px] leading-[1.125rem] text-wa-meta">{text.replace(/\n+/g, " ")}</span>
      </span>
    </span>
  );
}

const ROW = cn(
  "flex h-11 w-full items-center justify-center gap-1.5 border-t border-black/10 px-3 text-[15px] font-medium text-wa-button",
  "hover:bg-black/[0.03] aria-disabled:cursor-default aria-disabled:text-black/30 aria-disabled:hover:bg-transparent",
  FOCUS,
);

/** WhatsApp's reply buttons: a row each, with the reply arrow; a tapped one greys out. */
export function ReplyButtons({
  labels,
  spent,
  onPress,
}: {
  labels: readonly string[];
  spent: (index: number) => boolean;
  onPress: (index: number) => void;
}) {
  return (
    <div className="flex flex-col">
      {labels.map((label, index) => {
        const used = spent(index);
        return (
          <button
            key={label}
            type="button"
            aria-disabled={used || undefined}
            onClick={() => (used ? undefined : onPress(index))}
            className={ROW}
          >
            <Reply className="size-[1.125rem] shrink-0" aria-hidden="true" />
            <span>
              <Line text={label} />
            </span>
          </button>
        );
      })}
    </div>
  );
}

/** A WhatsApp list message's button: it opens the list sheet. */
export function ListButton({
  label,
  spent,
  onOpen,
  ref,
}: {
  label: string;
  spent: boolean;
  onOpen: () => void;
  ref?: Ref<HTMLButtonElement>;
}) {
  return (
    <button
      ref={ref}
      type="button"
      aria-haspopup="dialog"
      aria-disabled={spent || undefined}
      onClick={() => (spent ? undefined : onOpen())}
      className={ROW}
    >
      <List className="size-[1.125rem] shrink-0" aria-hidden="true" />
      {label}
    </button>
  );
}

/** WhatsApp's chat bar: back, FinBoy's photo (cropped round, as WhatsApp does), name, actions. */
export function TopBar({ typing }: { typing: boolean }) {
  return (
    <div aria-hidden="true" className="flex h-14 shrink-0 items-center bg-wa-bar pr-3.5 pl-2 text-wa-text shadow-[0_1px_0_rgb(11_20_26/0.06)]">
      <ArrowLeft className="size-6 shrink-0" />
      <span className="ml-1 size-9 shrink-0 overflow-hidden rounded-full">
        <BrandMark className="size-full" />
      </span>
      <span className="ml-3 min-w-0 flex-1">
        <span className="block truncate text-[17px] leading-tight font-medium">FinBoy</span>
        {typing ? <span className="block text-[13px] leading-tight text-wa-meta">typing…</span> : null}
      </span>
      <span className="flex shrink-0 items-center gap-5 max-[360px]:gap-3.5">
        <Video className="size-[1.375rem]" />
        <Phone className="size-5" />
        <EllipsisVertical className="size-5" />
      </span>
    </div>
  );
}

/** The message bar while FinBoy isn't waiting for anything typed: drawn only, nothing to focus. */
export function IdleBar() {
  return (
    <div aria-hidden="true" className="flex shrink-0 items-center gap-1.5 px-1.5 pt-1 pb-2">
      <div className={cn("flex h-12 min-w-0 flex-1 items-center gap-3 rounded-full bg-wa-bar px-3 text-wa-icon", BUBBLE_SHADOW)}>
        <FaceSlightlySmiling className="size-6 shrink-0" />
        <span className="min-w-0 flex-1 truncate text-[17px] text-wa-meta">Message</span>
        <Paperclip className="size-[1.375rem] shrink-0 -rotate-45" />
        <Camera className="size-[1.375rem] shrink-0" />
      </div>
      <span className="grid size-12 shrink-0 place-items-center rounded-full bg-wa-accent text-white">
        <Mic className="size-6" />
      </span>
    </div>
  );
}
