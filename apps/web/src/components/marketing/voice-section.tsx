"use client";

import { ChevronDown, Mic, Sparkles } from "lucide-react";
import { AnimatePresence, motion, useInView, useReducedMotion } from "motion/react";
import { useEffect, useRef, useState } from "react";

import { AnimatedAmount } from "@/components/motion/animated-amount";
import { EASE_OUT_EXPO, Reveal } from "@/components/motion/reveal";
import { SceneSlot } from "@/components/three/scene-slot";
import type { VoiceOrbState } from "@/components/three/scene-spec";
import { cn } from "@/lib/utils";

type Language = "ml" | "manglish" | "en";

const SCRIPT: Record<Language, { label: string; lang: string; question: string; answer: string }> = {
  ml: {
    label: "മലയാളം",
    lang: "ml",
    question: "ഈ മാസം ഭക്ഷണത്തിന് എത്ര ചെലവായി?",
    answer: "ഈ മാസം ഇതുവരെ ഭക്ഷണത്തിനായി 7,860 രൂപ ചെലവായിട്ടുണ്ട്.",
  },
  manglish: {
    label: "Manglish",
    lang: "en-IN",
    question: "Ee masam foodinu ethra poyi?",
    answer: "Ee masam ithuvare foodinu ₹7,860 poyi — confirmed records.",
  },
  en: {
    label: "English",
    lang: "en-IN",
    question: "How much did I spend on food this month?",
    answer: "You’ve spent ₹7,860 on food this month, across confirmed records.",
  },
};

const BREAKDOWN = [
  { merchant: "Hotel Arya", amountMinor: 125_000, note: "you corrected this" },
  { merchant: "Swiggy", amountMinor: 84_200 },
  { merchant: "Zomato", amountMinor: 61_300 },
  { merchant: "Café Kochi", amountMinor: 48_000 },
] as const;

// Starts on "idle" (full question and answer) so SSR, no-JS and reduced motion all show the complete exchange.
const PHASES: Array<{ state: VoiceOrbState; ms: number }> = [
  { state: "idle", ms: 2600 },
  { state: "listening", ms: 2600 },
  { state: "thinking", ms: 1400 },
  { state: "speaking", ms: 3800 },
];
const LISTENING = 1;

const STATUS: Record<VoiceOrbState, string> = {
  idle: "Illustrative demo",
  listening: "Listening…",
  thinking: "Checking your ledger…",
  speaking: "Speaking in your language",
};

export function VoiceSection() {
  const [language, setLanguage] = useState<Language>("manglish");
  const [phase, setPhase] = useState(0);
  const [typed, setTyped] = useState(0);
  const level = useRef(0);
  const root = useRef<HTMLElement>(null);
  const inView = useInView(root, { margin: "-20% 0px" });
  const reduced = useReducedMotion();
  const script = SCRIPT[language];
  const state = PHASES[phase]?.state ?? "idle";

  // Drive the demo loop only while the section is on screen.
  useEffect(() => {
    if (!inView || reduced) return;
    const timer = window.setTimeout(() => {
      const next = (phase + 1) % PHASES.length;
      if (next === LISTENING) setTyped(0);
      setPhase(next);
    }, PHASES[phase]?.ms ?? 2000);
    return () => window.clearTimeout(timer);
  }, [inView, phase, reduced]);

  // Typewriter for the spoken question while "listening".
  useEffect(() => {
    if (state !== "listening") return;
    const characters = Array.from(script.question).length;
    const step = window.setInterval(() => setTyped((count) => Math.min(count + 1, characters)), 2200 / characters);
    return () => {
      window.clearInterval(step);
    };
  }, [state, script.question]);

  // Simulated voice level for the orb (mic while listening, speech while speaking).
  useEffect(() => {
    let frame = 0;
    const tick = (time: number) => {
      const seconds = time / 1000;
      const speaking = state === "listening" || state === "speaking";
      level.current = speaking ? 0.22 + 0.55 * Math.abs(Math.sin(seconds * 8.3) * Math.sin(seconds * 3.1)) : 0;
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [state]);

  const question = Array.from(script.question);
  const questionShown = state === "listening" ? question.slice(0, typed).join("") : script.question;
  const answerVisible = state === "speaking" || state === "idle";

  function choose(next: Language) {
    setLanguage(next);
    setTyped(0);
    setPhase(0);
  }

  return (
    <section aria-label="Illustrative synthetic voice preview" ref={root} id="voice" aria-labelledby="voice-title" className="relative scroll-mt-24 overflow-hidden py-24 sm:py-28">
      <div aria-hidden="true" className="absolute inset-0 -z-10 bg-[radial-gradient(48rem_32rem_at_78%_40%,rgba(125,150,255,0.18),transparent_70%),radial-gradient(40rem_28rem_at_10%_80%,rgba(214,58,249,0.08),transparent_70%)]" />
      <div className="mx-auto grid max-w-[1360px] items-center gap-14 px-6 sm:px-10 lg:grid-cols-[1.05fr_1fr] lg:px-16">
        <div>
          <Reveal>
            <p className="eyebrow text-violet">Malayalam · Manglish · English</p>
            <h2 id="voice-title" className="mt-4 text-[clamp(2.1rem,4.2vw,3.6rem)] leading-[1.05] font-semibold tracking-[-0.04em] text-ink">
              Ask your money,
              <br /> in your language.
            </h2>
            <p className="mt-5 max-w-lg text-[1.0625rem] leading-relaxed text-ink-soft">
              Speak the way you think. FinBoy answers from your verified ledger — the numbers come from
              code, never from a guess.
            </p>
          </Reveal>

          <Reveal delay={0.1} className="mt-8">
            <div role="group" aria-label="Answer language" className="glass inline-flex rounded-full p-1">
              {(Object.keys(SCRIPT) as Language[]).map((key) => (
                <button
                  key={key}
                  type="button"
                  aria-pressed={language === key}
                  onClick={() => choose(key)}
                  lang={SCRIPT[key].lang}
                  className={cn(
                    "relative rounded-full px-4 py-2 text-sm font-semibold transition-colors",
                    language === key ? "text-white" : "text-ink-soft hover:text-ink",
                  )}
                >
                  {language === key ? (
                    <motion.span
                      layoutId="voice-language"
                      className="absolute inset-0 rounded-full bg-ink"
                      transition={{ type: "spring", stiffness: 380, damping: 32 }}
                    />
                  ) : null}
                  <span className="relative">{SCRIPT[key].label}</span>
                </button>
              ))}
            </div>
          </Reveal>

          <Reveal delay={0.18} className="mt-6">
            <div className="surface rounded-[1.75rem] p-5 sm:p-6">
              <p className="sr-only" lang={script.lang}>
                Question: {script.question} Answer: {script.answer}
              </p>
              <div aria-hidden="true" className="flex justify-end">
                <p lang={script.lang} className="max-w-[85%] rounded-[1.25rem] rounded-br-md bg-ink px-4 py-3 text-[0.95rem] text-white">
                  <Mic className="mr-2 inline size-3.5 -translate-y-px opacity-70" />
                  {questionShown}
                  {state === "listening" ? <span className="ml-0.5 inline-block h-4 w-px animate-pulse bg-white/80 align-middle" /> : null}
                </p>
              </div>
              <AnimatePresence mode="wait">
                {answerVisible ? (
                  <motion.div
                    key={language}
                    aria-hidden="true"
                    initial={{ opacity: 0, y: 12, filter: "blur(6px)" }}
                    animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.7, ease: EASE_OUT_EXPO }}
                    className="mt-4 rounded-[1.25rem] rounded-bl-md bg-[#f4f1ff] p-4"
                  >
                    <p lang={script.lang} className="flex gap-2 text-[0.95rem] leading-relaxed text-ink">
                      <Sparkles className="mt-1 size-4 shrink-0 text-violet" />
                      {script.answer}
                    </p>
                    <div className="mt-4 flex items-end justify-between gap-4 border-t border-violet/10 pt-4">
                      <div>
                        <p className="text-xs font-semibold text-ink-soft">Food &amp; dining · October</p>
                        <AnimatedAmount amountMinor={786_000} className="text-3xl font-semibold tracking-[-0.03em] text-ink" />
                      </div>
                      <p className="text-right text-xs text-ink-soft">12 transactions · all confirmed</p>
                    </div>
                    <ul className="mt-4 grid gap-1.5 text-sm">
                      {BREAKDOWN.map((row) => (
                        <li key={row.merchant} className="flex items-center justify-between">
                          <span className="text-ink">
                            {row.merchant}
                            {"note" in row ? <span className="ml-2 rounded-full bg-white px-2 py-0.5 text-[11px] font-semibold text-violet">{row.note}</span> : null}
                          </span>
                          <span className="tabular text-ink-soft">
                            {new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(row.amountMinor / 100)}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </motion.div>
                ) : null}
              </AnimatePresence>
              <details className="group mt-4 text-sm text-ink-soft">
                <summary className="flex cursor-pointer list-none items-center gap-1.5 font-semibold text-violet">
                  How was this calculated?
                  <ChevronDown className="size-4 transition-transform group-open:rotate-180" aria-hidden="true" />
                </summary>
                <p className="mt-2 leading-relaxed">
                  Sum of 12 confirmed food &amp; dining transactions, 1–28 October. Two items still awaiting your
                  confirmation are excluded until you approve them.
                </p>
              </details>
            </div>
          </Reveal>
        </div>

        <div className="relative">
          <SceneSlot spec={{ name: "voice-orb", state, level }} className="mx-auto aspect-square w-full max-w-[560px]" />
          <div aria-live="polite" className="glass absolute bottom-8 left-1/2 flex -translate-x-1/2 items-center gap-2.5 rounded-full px-4 py-2 text-sm font-semibold text-ink">
            <span
              className={cn(
                "size-2 rounded-full",
                state === "listening" ? "animate-pulse bg-magenta" : state === "thinking" ? "animate-pulse bg-violet" : state === "speaking" ? "bg-sky" : "bg-ink-subtle",
              )}
            />
            {STATUS[state]}
          </div>
        </div>
      </div>
    </section>
  );
}
