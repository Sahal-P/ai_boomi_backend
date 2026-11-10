import {
  ArrowLeft,
  Camera,
  CheckCheck,
  EllipsisVertical,
  FaceSlightlySmiling,
  Mic,
  Paperclip,
  Phone,
  Play,
  Reply,
  User,
  Video,
} from "lucide-react";
import { Fragment, type ReactNode } from "react";

import { BrandMark } from "@/components/brand";
import { PremiumPill } from "@/components/billing/premium-pill";
import { cn } from "@/lib/utils";

/**
 * A synthetic WhatsApp chat with FinBoy's real replies (apps/api/src/finboy/services/whatsapp/english.py:
 * saved_many, saved, budget_line and the button titles), drawn the way WhatsApp for Android draws
 * it in light mode (the wa-* tokens in globals.css): plain lines, no bold, because FinBoy sends no
 * formatting. Decoration for sighted readers and plain text for screen readers.
 */

type Line = readonly [glyph: string, text: string];

const BUBBLE_SHADOW = "shadow-[0_1px_0.5px_rgb(11_20_26/0.13)]";

// A voice note's waveform: bar heights in px, fixed so every render matches.
const WAVE = [4, 7, 11, 6, 13, 17, 10, 6, 14, 18, 12, 8, 5, 10, 15, 9, 6, 12, 7, 4, 8, 13, 7, 4, 6, 9, 5, 4];

function Glyph({ children }: { children: string }) {
  return <span aria-hidden="true">{children} </span>;
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

/** A message bubble; a transparent border still outlines it in forced-colours mode. */
function Bubble({ from, className, children }: { from: "you" | "finboy"; className?: string; children: ReactNode }) {
  const you = from === "you";
  return (
    <div
      data-from={from}
      className={cn(
        "relative w-fit max-w-[85%] rounded-[7.5px] border border-transparent text-[15px] leading-5 text-wa-text",
        BUBBLE_SHADOW,
        you ? "ml-auto rounded-tr-none bg-wa-out" : "mr-auto rounded-tl-none bg-wa-in",
        className,
      )}
    >
      <Tail side={you ? "out" : "in"} />
      {children}
    </div>
  );
}

/** Keeps room on the last line for the time, as WhatsApp does; the time drops a line if needed. */
function Spacer({ sent = false }: { sent?: boolean }) {
  return <span aria-hidden="true" className={cn("inline-block h-3", sent ? "w-[4.5rem]" : "w-14")} />;
}

/** The time, and for your messages two grey ticks: delivered (FinBoy sends no read receipts). */
function Meta({ time, sent = false }: { time: string; sent?: boolean }) {
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

function Lines({ lines }: { lines: readonly Line[] }) {
  return (
    <p>
      {lines.map(([glyph, text], index) => (
        <Fragment key={text}>
          {index > 0 ? <br /> : null}
          <Glyph>{glyph}</Glyph>
          {text}
        </Fragment>
      ))}
      <Spacer />
    </p>
  );
}

/** WhatsApp's reply buttons: rows inside the bubble under a hairline, each with the reply arrow. */
function Buttons({ items }: { items: readonly Line[] }) {
  return (
    <p className="flex flex-col">
      <span className="sr-only">Buttons: </span>
      {items.map(([glyph, label], index) => (
        <span
          key={label}
          className="flex h-11 items-center justify-center gap-1.5 border-t border-black/10 px-3 text-[15px] font-medium text-wa-button"
        >
          <Reply className="size-[1.125rem] shrink-0" aria-hidden="true" />
          <span>
            <Glyph>{glyph}</Glyph>
            {label}
            {index < items.length - 1 ? <span className="sr-only">,</span> : null}
          </span>
        </span>
      ))}
    </p>
  );
}

function FinBoyReply({ lines, buttons, time }: { lines: readonly Line[]; buttons: readonly Line[]; time: string }) {
  return (
    <li>
      <Bubble from="finboy" className="min-w-[13.5rem]">
        <div className="relative px-2.5 pt-1.5 pb-2">
          <span className="sr-only">FinBoy: </span>
          <Lines lines={lines} />
          <Meta time={time} />
        </div>
        <Buttons items={buttons} />
      </Bubble>
    </li>
  );
}

/** WhatsApp's voice message: play, the waveform with its green knob, the length, your photo with
 *  a mic, and the transcript underneath. */
function VoiceNote({ transcript, length, time }: { transcript: string; length: string; time: string }) {
  return (
    <li>
      <Bubble from="you" className="w-[16.5rem] px-2 pt-2 pb-1.5">
        <span className="sr-only">You: Voice note, “{transcript}”</span>
        <div aria-hidden="true">
          <div className="flex items-center gap-2">
            <Play className="size-7 shrink-0 fill-current text-wa-meta" strokeWidth={1.5} />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1">
                <span className="size-3 shrink-0 rounded-full bg-wa-accent" />
                <svg viewBox={`0 0 ${WAVE.length * 4} 20`} className="h-5 min-w-0 flex-1 text-black/25" preserveAspectRatio="none">
                  {WAVE.map((height, index) => (
                    <rect key={index} x={index * 4 + 1} y={(20 - height) / 2} width="2" height={height} rx="1" fill="currentColor" />
                  ))}
                </svg>
              </div>
              <p className="mt-0.5 text-[11px] leading-4 text-wa-meta">{length}</p>
            </div>
            <span className="relative shrink-0">
              <span className="grid size-11 items-end justify-items-center overflow-hidden rounded-full bg-wa-avatar text-white">
                <User className="size-9 translate-y-1.5 fill-current" strokeWidth={1} />
              </span>
              <Mic className="absolute -bottom-0.5 -left-1.5 size-4 text-wa-accent" strokeWidth={2.5} />
            </span>
          </div>
          <p className="mt-1.5 px-0.5 text-wa-meta">
            “{transcript}”
            <Spacer sent />
          </p>
        </div>
        <Meta time={time} sent />
      </Bubble>
    </li>
  );
}

function YourText({ children, time }: { children: string; time: string }) {
  return (
    <li>
      <Bubble from="you" className="px-2.5 pt-1.5 pb-2">
        <p>
          <span className="sr-only">You: </span>
          {children}
          <Spacer sent />
        </p>
        <Meta time={time} sent />
      </Bubble>
    </li>
  );
}

/** WhatsApp's chat bar: back, FinBoy's photo (cropped round, as WhatsApp does), name, actions. */
function TopBar() {
  return (
    <div aria-hidden="true" className="flex h-14 items-center bg-wa-bar pr-3.5 pl-2 text-wa-text shadow-[0_1px_0_rgb(11_20_26/0.06)]">
      <ArrowLeft className="size-6 shrink-0" />
      <span className="ml-1 size-9 shrink-0 overflow-hidden rounded-full">
        <BrandMark className="size-full" />
      </span>
      <span className="ml-3 min-w-0 flex-1 truncate text-[17px] font-medium">FinBoy</span>
      <span className="flex shrink-0 items-center gap-5 max-[360px]:gap-3.5">
        <Video className="size-[1.375rem]" />
        <Phone className="size-5" />
        <EllipsisVertical className="size-5" />
      </span>
    </div>
  );
}

/** WhatsApp's message bar, drawn only: not a field, nothing to focus. */
function MessageBar() {
  return (
    <div aria-hidden="true" className="flex items-center gap-1.5 px-1.5 pt-1 pb-2">
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

export function ChatPreview() {
  return (
    <figure className="mx-auto w-full max-w-[24rem]">
      <div className="rounded-[2.4rem] bg-ink p-[7px] shadow-[0_30px_60px_-30px_rgb(14_16_19/0.55)]">
        <div className="overflow-hidden rounded-[2.05rem] bg-wa-wallpaper font-wa">
          <TopBar />
          <div className="bg-wa-wallpaper px-3 pt-3 pb-2">
            <p
              aria-hidden="true"
              className={cn("mx-auto w-fit rounded-[7.5px] bg-wa-in px-3 py-1 text-[12.5px] leading-4 text-wa-meta", BUBBLE_SHADOW)}
            >
              Today
            </p>
            <ol className="mt-3 space-y-2.5" aria-label="Example chat with FinBoy">
              <YourText time="8:02 pm">chai 20, auto 50, lunch 120</YourText>
              <FinBoyReply
                time="8:02 pm"
                lines={[
                  ["✅", "Saved 3 · ₹190"],
                  ["•", "₹20 · Food & dining"],
                  ["•", "₹50 · Transport"],
                  ["•", "₹120 · Food & dining"],
                ]}
                buttons={[
                  ["↩️", "Undo all"],
                  ["✏️", "Fix one"],
                ]}
              />
              <VoiceNote transcript="Paid the milkman 500" length="0:03" time="8:05 pm" />
              <FinBoyReply
                time="8:05 pm"
                lines={[
                  ["✅", "Saved: ₹500 paid"],
                  ["🏷️", "Groceries"],
                  ["👤", "milkman"],
                  ["📅", "Today"],
                  ["🟢", "Groceries: ₹2,300 of ₹6,000 this month"],
                ]}
                buttons={[
                  ["↩️", "Undo"],
                  ["✏️", "Amount"],
                  ["🏷️", "Category"],
                ]}
              />
            </ol>
          </div>
          <MessageBar />
        </div>
      </div>
      <figcaption className="mt-4 px-1 text-xs leading-relaxed text-ink-soft">
        Synthetic example. The replies and buttons are the ones FinBoy sends. Voice notes need{" "}
        <PremiumPill className="align-middle" />
      </figcaption>
    </figure>
  );
}
