"use client";

import { RotateCcw } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { PremiumPill } from "@/components/billing/premium-pill";
import { useMediaQuery } from "@/hooks/use-media-query";
import { CLIPS, deliver, initialChat, tap, usedKey, type ChatState, type Message, type Tap } from "@/lib/chat-demo/script";
import { cn } from "@/lib/utils";

import { AmountBar } from "./chat/amount-bar";
import { BUBBLE_SHADOW, Bubble, IdleBar, ListButton, MessageText, Meta, Quote, ReplyButtons, TopBar } from "./chat/bubbles";
import { ListSheet } from "./chat/list-sheet";
import { VoiceNote } from "./chat/voice-note";

/** How long FinBoy shows "typing…" before each reply. */
const TYPING_MS = 700;
/** The opening chat's next minute: the first tap moves it on. */
const OPENING_MINUTE = initialChat().minute;

const side = (message: Message) =>
  message.kind === "sent" ? "you" : message.kind === "reply" ? "finboy" : message.from;

/**
 * The landing's live WhatsApp chat with FinBoy. The script, with FinBoy's real replies, is in
 * lib/chat-demo/script.ts. Visitors can play the voice notes, tap the buttons, pick from the lists
 * and type an amount.
 *
 * The opening chat renders on the server. Everything after it runs in the browser and sends
 * nothing. From the first tap the phone keeps its height, and new messages scroll inside it.
 */
export function ChatPreview() {
  const [chat, setChat] = useState<ChatState>(initialChat);
  const [typing, setTyping] = useState(false);
  const [playing, setPlaying] = useState<number | null>(null);
  const [sheet, setSheet] = useState<number | null>(null);
  const [height, setHeight] = useState<number | null>(null);
  const [round, setRound] = useState(0);
  const screen = useRef<HTMLDivElement>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const timer = useRef<number | undefined>(undefined);
  const lists = useRef(new Map<number, HTMLButtonElement>());
  const returnTo = useRef<number | null>(null);
  const reduced = useMediaQuery("(prefers-reduced-motion: reduce)");

  useEffect(() => () => window.clearTimeout(timer.current), []);

  // Focus goes back to the list's button once the sheet is gone and the chat is no longer inert.
  useEffect(() => {
    if (sheet !== null || returnTo.current === null) return;
    lists.current.get(returnTo.current)?.focus({ preventScroll: true });
    returnTo.current = null;
  }, [sheet]);

  useEffect(() => {
    const element = scroller.current;
    if (!element || height === null) return;
    element.scrollTo({ top: element.scrollHeight, behavior: reduced ? "auto" : "smooth" });
  }, [chat.messages.length, height, reduced]);

  /** Your message now, FinBoy's after "typing…"; false while FinBoy is still typing. */
  const send = (input: Tap): boolean => {
    if (typing) return false;
    const turn = tap(chat, input);
    if (!turn) return false;
    if (height === null && screen.current) setHeight(screen.current.getBoundingClientRect().height);
    setChat(turn.sent);
    setTyping(true);
    timer.current = window.setTimeout(() => {
      setChat((current) => deliver(current, turn.replies));
      setTyping(false);
    }, TYPING_MS);
    return true;
  };

  const closeSheet = (then?: (message: number) => void) => {
    const message = sheet;
    returnTo.current = message;
    setSheet(null);
    if (message !== null) then?.(message);
  };

  const reset = () => {
    window.clearTimeout(timer.current);
    setChat(initialChat());
    setTyping(false);
    setPlaying(null);
    setSheet(null);
    setHeight(null);
    setRound((value) => value + 1);
    scroller.current?.scrollTo({ top: 0 });
  };

  const listing = chat.messages.find((message) => message.id === sheet);

  function render(message: Message, tail: boolean) {
    if (message.kind === "voice") {
      return (
        <VoiceNote
          from={message.from}
          clip={CLIPS[message.clip]}
          time={message.time}
          tail={tail}
          playing={playing === message.id}
          onToggle={(on) => setPlaying(on ? message.id : null)}
        />
      );
    }
    if (message.kind === "sent") {
      return (
        <Bubble from="you" tail={tail} className="px-1 pt-1 pb-2">
          {message.quote ? <Quote text={message.quote} /> : null}
          <p className="px-1.5 pt-0.5">
            <span className="sr-only">You: </span>
            <MessageText text={message.text} sent />
          </p>
          <Meta time={message.time} sent />
        </Bubble>
      );
    }
    const { buttons, listing: list } = message;
    return (
      <Bubble from="finboy" tail={tail} className={buttons || list ? "min-w-[13.5rem]" : undefined}>
        <div className="relative px-2.5 pt-1.5 pb-2">
          <p>
            <span className="sr-only">FinBoy: </span>
            <MessageText text={message.text} />
          </p>
          <Meta time={message.time} />
        </div>
        {buttons ? (
          <ReplyButtons
            labels={buttons.map((button) => button.label)}
            spent={(index) => chat.used.includes(usedKey(message.id, index))}
            onPress={(index) => send({ kind: "button", message: message.id, index })}
          />
        ) : null}
        {list ? (
          <ListButton
            ref={(element) => {
              if (element) lists.current.set(message.id, element);
              else lists.current.delete(message.id);
            }}
            label={list.open}
            spent={chat.used.includes(usedKey(message.id, "list"))}
            onOpen={() => setSheet(message.id)}
          />
        ) : null}
      </Bubble>
    );
  }

  return (
    <figure className="mx-auto w-full max-w-[24rem]">
      <div
        ref={screen}
        data-wa-screen=""
        className="wa-wallpaper relative flex flex-col overflow-hidden rounded-[1.75rem] font-wa shadow-[0_24px_56px_-24px_rgb(14_16_19/0.4)] ring-1 ring-black/[0.06]"
        style={height === null ? undefined : { height }}
      >
        <TopBar typing={typing} />
        <div ref={scroller} inert={sheet !== null} className="min-h-0 flex-1 overflow-y-auto px-3 pt-3 pb-2">
          <p
            aria-hidden="true"
            className={cn("mx-auto w-fit rounded-[7.5px] bg-wa-in px-3 py-1 text-[12.5px] leading-4 text-wa-meta", BUBBLE_SHADOW)}
          >
            Today
          </p>
          <ol key={round} aria-label="Example chat with FinBoy" aria-live="polite" aria-relevant="additions" className="mt-3">
            {chat.messages.map((message, index) => {
              const before = chat.messages[index - 1];
              const tail = !before || side(before) !== side(message);
              return (
                <li key={message.id} className={tail ? "mt-2.5 first:mt-0" : "mt-0.5"}>
                  {render(message, tail)}
                </li>
              );
            })}
          </ol>
        </div>
        <div inert={sheet !== null}>
          {chat.awaiting ? <AmountBar onSend={(text) => send({ kind: "amount", text })} /> : <IdleBar />}
        </div>
        {listing?.kind === "reply" && listing.listing ? (
          <ListSheet
            listing={listing.listing}
            onClose={() => closeSheet()}
            onPick={(index) => closeSheet((message) => send({ kind: "row", message, index }))}
          />
        ) : null}
      </div>
      <figcaption className="mt-4 px-1 text-xs leading-relaxed text-ink-soft">
        Try it: play a voice note or tap a button. A synthetic example with AI voices: the replies and
        buttons are the ones FinBoy sends. Voice notes need <PremiumPill className="align-middle" />
        {chat.minute > OPENING_MINUTE ? (
          <span className="mt-1 block">
            <button
              type="button"
              onClick={reset}
              className="inline-flex min-h-11 items-center gap-1.5 font-semibold text-ink underline-offset-4 hover:underline"
            >
              <RotateCcw className="size-3.5" aria-hidden="true" />
              Start again
            </button>
          </span>
        ) : null}
      </figcaption>
    </figure>
  );
}
