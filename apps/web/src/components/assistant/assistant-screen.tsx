"use client";

import { ArrowDown, Calculator, PiggyBank, SquarePen, UtensilsCrossed, Wallet } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useId, useRef, useState } from "react";
import { Composer } from "@/components/assistant/composer";
import { TurnCard } from "@/components/assistant/turn-card";
import { ThinkingOrb } from "@/components/feedback/thinking-orb";
import { Button } from "@/components/ui/button";
import { useAssistant } from "@/hooks/use-assistant";
import { useSpeech } from "@/hooks/use-speech";
import { useVoiceRecorder } from "@/hooks/use-voice-recorder";
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
  const assistant = useAssistant();
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
    if (assistant.ask(text)) {
      setDraft("");
      setFromVoice(false);
      voice.reset();
    }
  }

  function newChat() {
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
        {!empty && (
          <Button variant="ghost" size="sm" onClick={newChat}>
            <SquarePen aria-hidden="true" /> New chat
          </Button>
        )}
      </header>

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
            {turns.map((turn) => {
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
              voice={voice}
              fromVoice={fromVoice}
              onDiscardTranscript={() => {
                setDraft("");
                setFromVoice(false);
                voice.reset();
              }}
            />
            <p className="mt-2 text-center text-xs text-ink-soft">
              FinBoy answers from your confirmed records and never picks funds or stocks.
            </p>
          </div>
        </motion.div>

        {empty && (
          <ul aria-label="Suggested questions" className="mt-6 flex flex-wrap justify-center gap-2">
            {SUGGESTIONS.map((suggestion, index) => (
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
