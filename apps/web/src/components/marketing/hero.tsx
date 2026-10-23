import { ArrowRight, Play, ShieldCheck } from "lucide-react";
import Link from "next/link";
import type { CSSProperties } from "react";

import { HeroStage } from "./hero-stage";

const lines = ["Your inbox", "already knows", "your money."] as const;
const assurances = ["Read-only Gmail access", "Raw emails never stored", "Disconnect anytime"] as const;

function delay(seconds: number): CSSProperties {
  return { animationDelay: `${seconds}s` };
}

export function Hero() {
  return (
    <section
      aria-labelledby="hero-title"
      className="relative isolate min-h-[100svh] overflow-hidden bg-[#efedf6]"
    >
      <HeroStage />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 z-[1] hidden bg-[linear-gradient(90deg,rgba(239,237,246,0.94)_0%,rgba(239,237,246,0.7)_32%,rgba(239,237,246,0)_60%)] md:block"
      />
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 z-[1] h-[78%] bg-[linear-gradient(180deg,rgba(239,237,246,0.97)_0%,rgba(239,237,246,0.9)_58%,rgba(239,237,246,0)_100%)] md:hidden"
      />
      <div className="relative z-[2] mx-auto flex min-h-[100svh] max-w-[1360px] flex-col justify-start px-6 pt-32 pb-24 sm:px-10 md:justify-center md:pt-24 lg:px-16">
        <p
          className="rise-in eyebrow glass inline-flex w-fit items-center gap-2 rounded-full px-3.5 py-1.5 text-violet"
          style={delay(0.1)}
        >
          <span className="size-1.5 rounded-full bg-violet shadow-[0_0_0_4px_rgba(109,74,255,0.16)]" />
          Email-native money copilot
        </p>
        <h1
          id="hero-title"
          className="mt-7 max-w-[13ch] text-[clamp(2.85rem,6.4vw,5.6rem)] leading-[1.02] font-semibold tracking-[-0.045em] text-ink"
        >
          {lines.map((line, index) => (
            <span key={line} className="line-mask">
              <span className="line-up" style={delay(0.15 + index * 0.1)}>
                {line}
              </span>{" "}
            </span>
          ))}
        </h1>
        <p
          className="rise-in mt-7 max-w-[30rem] text-[1.0625rem] leading-relaxed text-ink-soft"
          style={delay(0.55)}
        >
          FinBoy turns bank alerts, receipts and bills into a tracked money timeline — then
          answers your questions in Hindi, English, Malayalam and supported romanized text.
        </p>
        <div className="rise-in mt-9 flex flex-wrap items-center gap-3" style={delay(0.7)}>
          <Link
            href="/connect"
            className="group inline-flex h-12 items-center gap-3 rounded-full bg-ink pr-2 pl-6 text-sm font-semibold text-white shadow-lift transition-transform duration-300 ease-out-expo hover:-translate-y-0.5"
          >
            Connect Gmail
            <span className="grid size-8 place-items-center rounded-full bg-white/15 transition-transform duration-300 ease-out-expo group-hover:translate-x-0.5">
              <ArrowRight className="size-4" aria-hidden="true" />
            </span>
          </Link>
          <Link
            href="/connect"
            className="glass inline-flex h-12 items-center gap-2.5 rounded-full px-6 text-sm font-semibold text-ink transition-transform duration-300 ease-out-expo hover:-translate-y-0.5"
          >
            <Play className="size-3.5 fill-current" aria-hidden="true" />
            Try the demo mailbox
          </Link>
        </div>
        <ul
          className="rise-in mt-10 flex flex-wrap gap-x-6 gap-y-2 text-[13px] font-medium text-ink-soft"
          style={delay(0.85)}
        >
          {assurances.map((item) => (
            <li key={item} className="flex items-center gap-2">
              <ShieldCheck className="size-4 text-violet" aria-hidden="true" />
              {item}
            </li>
          ))}
        </ul>
      </div>
      <div
        aria-hidden="true"
        className="rise-in absolute bottom-7 left-1/2 z-[2] hidden -translate-x-1/2 flex-col items-center gap-2 text-[11px] font-semibold tracking-[0.2em] text-ink-subtle md:flex"
        style={delay(1.2)}
      >
        SCROLL
        <span className="relative h-10 w-px overflow-hidden bg-ink/10">
          <span className="absolute inset-x-0 top-0 h-1/2 animate-[scroll-cue_2.4s_var(--ease-in-out-quint)_infinite] bg-violet" />
        </span>
      </div>
    </section>
  );
}
