"use client";

import { ArrowDown, Calculator, History, MessageCircle, PiggyBank, SquarePen, UtensilsCrossed, Wallet } from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import { useHouseholdAccess } from "@/components/app-shell/household-context";
import { Composer } from "@/components/assistant/composer";
import { PremiumPill } from "@/components/billing/premium-pill";
import { usePremium } from "@/components/billing/premium-provider";
import { TurnCard } from "@/components/assistant/turn-card";
import { ThinkingOrb } from "@/components/feedback/thinking-orb";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useAssistant } from "@/hooks/use-assistant";
import { useSpeech } from "@/hooks/use-speech";
import { useResource } from "@/hooks/use-resource";
import { useVoiceRecorder } from "@/hooks/use-voice-recorder";
import { getSuggestions, listThreads, type ChatThread } from "@/lib/api/assistant";
import { describeProblem, type Problem } from "@/lib/messages";
import { cn } from "@/lib/utils";

const SUGGESTIONS: { text: string; lang?: string; icon?: typeof Wallet }[] = [
  { text: "How much did I spend this month?", icon: Wallet },
  { text: "How much did I spend on food this month?", icon: UtensilsCrossed },
  { text: "How much money is left this month?", icon: PiggyBank },
  { text: "Can I set aside ₹5,000 each month?", icon: Calculator },
  { text: "इस महीने कितना पैसा बाकी है?", lang: "hi" },
  { text: "ഈ മാസം ഭക്ഷണത്തിന് എത്ര ചെലവായി?", lang: "ml" },
];

const istHour = new Intl.DateTimeFormat("en-GB", { hour: "numeric", hourCycle: "h23", timeZone: "Asia/Kolkata" });

/** A time-of-day hello. FinBoy keeps no name, so it never pretends to know one. */
function greeting(now: Date) {
  const hour = Number(istHour.format(now));
  if (hour >= 5 && hour < 12) return "Good morning";
  if (hour >= 12 && hour < 17) return "Good afternoon";
  if (hour >= 17 && hour < 22) return "Good evening";
  return "Hello";
}

const chatDay = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short", timeZone: "Asia/Kolkata" });

/** Earlier chats with FinBoy, on the web and WhatsApp; opening one continues it. */
function RecentChats({
  open,
  generation,
  onOpenChange,
  onPick,
}: {
  open: boolean;
  /** Changes each time the sheet opens, so the list is fetched fresh. */
  generation: number;
  onOpenChange: (open: boolean) => void;
  onPick: (thread: ChatThread) => void;
}) {
  const chats = useResource(open ? `chats-${generation}` : null, (signal) => listThreads(signal));
  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="p-5">
        <SheetHeader className="p-0">
          <SheetTitle className="text-xl">Recent chats</SheetTitle>
          <SheetDescription>Pick up where you left off, here or on WhatsApp.</SheetDescription>
        </SheetHeader>
        {chats.status === "loading" && <p className="text-sm text-ink-soft">Loading your chats…</p>}
        {chats.error !== null && (
          <ProblemNotice problem={describeProblem(chats.error, "FinBoy couldn't load your chats")} onRetry={chats.reload} />
        )}
        {chats.data?.length === 0 && (
          <p className="text-sm text-ink-soft">No chats yet. Ask anything about your money to start one.</p>
        )}
        {chats.data && chats.data.length > 0 && (
          <ul className="-mx-2 flex-1 space-y-1 overflow-y-auto">
            {chats.data.map((thread) => (
              <li key={thread.id}>
                <button
                  type="button"
                  onClick={() => onPick(thread)}
                  className="flex min-h-11 w-full items-start gap-3 rounded-2xl px-3 py-2.5 text-left hover:bg-white/60"
                >
                  <MessageCircle className="mt-0.5 size-4 shrink-0 text-ink-soft" aria-hidden="true" />
                  <span className="min-w-0 flex-1">
                    <span className="block font-semibold break-words text-ink">{thread.title || "Chat"}</span>
                    <span className="block text-xs text-ink-soft">
                      {chatDay.format(new Date(thread.last_at))}
                      {thread.channel === "whatsapp" ? " · WhatsApp" : ""} · {Math.ceil(thread.messages / 2)}{" "}
                      {thread.messages > 2 ? "questions" : "question"}
                    </span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </SheetContent>
    </Sheet>
  );
}

/** To the bottom of the page, where the conversation's end always sits clear of the docked composer. */
function scrollToEnd() {
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  window.scrollTo({ top: document.documentElement.scrollHeight, behavior: reduce ? "auto" : "smooth" });
}

/**
 * Ask, laid out like a chat: a greeting and suggestions until the first question, then the
 * conversation oldest-first with the composer docked below it. Questions and answers live in
 * memory only (lib/conversation.ts).
 */
export function AssistantScreen() {
  const premium = usePremium();
  const { advisor } = useHouseholdAccess();
  // With the advisor on, every household can ask by typing; voice stays part of Premium.
  const canAsk = premium.premium || advisor;
  const assistant = useAssistant();
  const [chatsOpen, setChatsOpen] = useState(false);
  const [chatsGeneration, setChatsGeneration] = useState(0);
  const [openProblem, setOpenProblem] = useState<Problem | null>(null);
  const [personal, setPersonal] = useState<string[] | null>(null);
  const speech = useSpeech();
  const [draft, setDraft] = useState("");
  const [fromVoice, setFromVoice] = useState(false);
  const voice = useVoiceRecorder((transcript) => {
    setDraft(transcript);
    setFromVoice(true);
  });
  const ids = useId();
  const input = useRef<HTMLTextAreaElement>(null);
  const end = useRef<HTMLDivElement>(null);
  const [atEnd, setAtEnd] = useState(true);
  const [hello] = useState(() => greeting(new Date()));
  const turns = [...assistant.turns].reverse();
  const empty = turns.length === 0;

  // Starter questions from the household's own figures, when the advisor is on.
  useEffect(() => {
    if (!advisor || !empty) return;
    const controller = new AbortController();
    getSuggestions(controller.signal).then(
      (found) => setPersonal(found),
      () => undefined, // the fixed suggestions stay
    );
    return () => controller.abort();
  }, [advisor, empty]);
  const suggestions: typeof SUGGESTIONS = personal?.length
    ? [...personal.map((text) => ({ text })), ...SUGGESTIONS.filter((item) => item.lang)]
    : SUGGESTIONS;
  const latest = assistant.turns[0];
  const latestId = latest?.id ?? null;
  const latestState = latest?.state ?? null;

  // A new question always scrolls to the end; its answer does only if you were already there.
  const following = useRef(true);
  useEffect(() => {
    following.current = atEnd;
  }, [atEnd]);
  useEffect(() => {
    if (latestId) scrollToEnd();
  }, [latestId]);
  useEffect(() => {
    if (latestState && latestState !== "pending" && following.current) scrollToEnd();
  }, [latestState]);

  // "At the end" means the last answer is visible above the docked composer.
  useEffect(() => {
    const target = end.current;
    if (!target) return;
    const observer = new IntersectionObserver(([entry]) => setAtEnd(entry?.isIntersecting ?? true), {
      rootMargin: "0px 0px -180px 0px",
    });
    observer.observe(target);
    return () => observer.disconnect();
  }, [empty]);

  function submit(text = draft) {
    // On the Free plan the question stays in the box while the upgrade sheet explains Premium.
    if (!canAsk) {
      if (text.trim()) setDraft(text);
      premium.open("ask");
      return;
    }
    if (assistant.ask(text)) {
      setDraft("");
      setFromVoice(false);
      voice.reset();
    }
  }

  async function openChat(thread: ChatThread) {
    setChatsOpen(false);
    setOpenProblem(null);
    try {
      await assistant.open(thread.id);
    } catch (error) {
      setOpenProblem(describeProblem(error, "FinBoy couldn't open that chat"));
    }
  }

  function newChat() {
    setOpenProblem(null);
    assistant.clear();
    setDraft("");
    setFromVoice(false);
    voice.reset();
    input.current?.focus();
  }

  return (
    <div className="ask-page mx-auto flex min-h-[calc(100dvh-10.75rem)] max-w-3xl flex-col lg:min-h-[calc(100dvh-4rem)]">
      <header className="flex min-h-11 items-center justify-between gap-3">
        <h1 className="text-lg font-semibold tracking-[-0.01em]">Ask FinBoy</h1>
        <div className="flex items-center gap-1">
          {advisor && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setChatsGeneration((value) => value + 1);
                setChatsOpen(true);
              }}
            >
              <History aria-hidden="true" /> Recent chats
            </Button>
          )}
          {!empty && (
            <Button variant="ghost" size="sm" onClick={newChat}>
              <SquarePen aria-hidden="true" /> New chat
            </Button>
          )}
        </div>
      </header>
      {advisor && (
        <RecentChats
          open={chatsOpen}
          generation={chatsGeneration}
          onOpenChange={setChatsOpen}
          onPick={(thread) => void openChat(thread)}
        />
      )}
      {openProblem && <ProblemNotice problem={openProblem} className="mt-3" />}

      <div className={cn("flex flex-1 flex-col", empty && "justify-center")}>
        {empty ? (
          <section aria-labelledby={`${ids}-hello`} className="pb-8 text-center">
            <ThinkingOrb state="breathing" rest className="mx-auto" />
            <h2 id={`${ids}-hello`} className="rise-in mt-6 text-[2rem] leading-tight font-medium tracking-[-0.035em] sm:text-[2.6rem]">
              {hello}
            </h2>
            <p className="rise-in mt-2 text-base text-ink-soft [animation-delay:120ms]">
              Ask about your money in English, <span lang="hi">हिन्दी</span> or <span lang="ml">മലയാളം</span>.
            </p>
          </section>
        ) : (
          <section role="log" aria-label="Conversation" className="flex flex-1 flex-col gap-10 pt-6 pb-10">
            {turns.map((turn, index) => {
              const last = index === turns.length - 1;
              return (
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
                  followUps={last && turn.state === "answered" ? (turn.answer?.follow_ups ?? []) : []}
                  onFollowUp={(question) => submit(question)}
                />
              );
            })}
            <div ref={end} />
          </section>
        )}

        {!empty && <div aria-hidden="true" className="ask-fade" />}
        {/* One composer for both layouts, so typing and focus survive the first question while it
            glides from the middle of the screen down to its dock. */}
        <motion.div layout="position" transition={{ type: "spring", stiffness: 260, damping: 32 }} className="sticky bottom-[5.5rem] z-30 lg:bottom-6">
          <div className="relative">
            {!empty && !atEnd && (
              <Button
                variant="glass"
                size="icon"
                aria-label="Jump to the latest answer"
                className="absolute -top-14 left-1/2 size-10 -translate-x-1/2 bg-white/90"
                onClick={scrollToEnd}
              >
                <ArrowDown aria-hidden="true" />
              </Button>
            )}
            <Composer
              id={`${ids}-question`}
              inputRef={input}
              value={draft}
              onChange={setDraft}
              onSubmit={() => submit()}
              pending={assistant.pending}
              onStop={assistant.cancel}
              style={assistant.style}
              onStyle={assistant.setStyle}
              voice={premium.premium ? voice : { ...voice, start: () => premium.open("voice") }}
              fromVoice={fromVoice}
              onDiscardTranscript={() => {
                setDraft("");
                setFromVoice(false);
                voice.reset();
              }}
            />
            {advisor ? (
              <p className="mt-2 text-center text-xs text-ink-soft">
                FinBoy answers from your records, remembers what you tell it (
                <Link href="/memory" className="font-semibold text-ink underline underline-offset-2">
                  Memory
                </Link>
                ) and never picks funds or stocks.
              </p>
            ) : premium.premium ? (
              <p className="mt-2 text-center text-xs text-ink-soft">
                FinBoy answers from your confirmed records and never picks funds or stocks.
              </p>
            ) : (
              <p className="mt-2 flex items-center justify-center gap-2 text-center text-xs text-ink-soft">
                <PremiumPill />
                Asking FinBoy is part of Premium.
                <button type="button" className="font-semibold text-ink underline underline-offset-2" onClick={() => premium.open("ask")}>
                  See Premium
                </button>
              </p>
            )}
          </div>
        </motion.div>

        {empty && (
          <ul aria-label="Suggested questions" className="mt-6 flex flex-wrap justify-center gap-2">
            {suggestions.map((suggestion, index) => (
              <li key={suggestion.text} className="rise-in" style={{ animationDelay: `${200 + index * 60}ms` }}>
                <button
                  type="button"
                  lang={suggestion.lang}
                  disabled={assistant.pending}
                  onClick={() => submit(suggestion.text)}
                  className="surface inline-flex min-h-11 items-center gap-2 rounded-full px-4 py-2 text-left text-sm text-ink transition-[transform,background-color] duration-300 ease-out-expo hover:-translate-y-px hover:bg-white/80"
                >
                  {suggestion.icon && <suggestion.icon className="size-4 shrink-0 text-ink-soft" aria-hidden="true" />}
                  {suggestion.text}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
