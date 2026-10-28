import { ChevronsRight, Play, ShieldCheck } from "lucide-react";
import Link from "next/link";
import type { CSSProperties } from "react";

import { MoneyScene } from "@/components/illustrations/scenes";
import { WhatsAppStart } from "@/components/marketing/whatsapp-start";

const lines = ["Your inbox", "already knows", "your money."] as const;
const assurances = ["Read-only Gmail access", "Raw emails never stored", "Disconnect anytime"] as const;

function delay(seconds: number): CSSProperties {
  return { animationDelay: `${seconds}s` };
}

/** The landing hero is a yellow moment: flat sunflower, ink and the drawn money scene. */
export function Hero() {
  return (
    <section data-hero aria-labelledby="hero-title" className="moment relative isolate overflow-hidden">
      <div className="relative mx-auto grid min-h-[100svh] max-w-[1360px] content-center items-center gap-x-12 gap-y-10 px-6 pt-28 pb-20 sm:px-10 md:pt-24 lg:grid-cols-[1.05fr_1fr] lg:px-16">
        <div>
          <p
            className="rise-in eyebrow inline-flex w-fit items-center gap-2 rounded-full border-2 border-ink bg-white px-3.5 py-1.5 text-ink"
            style={delay(0.1)}
          >
            <span className="size-1.5 rounded-full bg-ink" />
            Email-native money copilot
          </p>
          <h1
            id="hero-title"
            className="mt-7 max-w-[13ch] text-[clamp(2.85rem,6.4vw,5.6rem)] leading-[1.0] font-extrabold tracking-[-0.05em] text-ink"
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
            className="rise-in mt-7 max-w-[30rem] text-[1.0625rem] leading-relaxed text-sunflower-ink"
            style={delay(0.55)}
          >
            FinBoy turns bank alerts, receipts and bills into a tracked money timeline — then
            answers your questions in Hindi, English, Malayalam and supported romanized text.
          </p>
          <div className="rise-in mt-9 flex flex-wrap items-center gap-3" style={delay(0.7)}>
            <Link
              href="/login"
              className="group inline-flex h-14 items-center gap-3 rounded-full bg-ink p-1 pr-7 text-sm font-semibold text-white shadow-lift transition-transform duration-300 ease-out-expo hover:-translate-y-0.5"
            >
              {/* The reference's chevron capsule, as decoration on an ordinary link. */}
              <span className="grid h-12 w-16 place-items-center rounded-full bg-white text-ink transition-transform duration-300 ease-out-expo group-hover:translate-x-0.5">
                <ChevronsRight className="size-5" aria-hidden="true" />
              </span>
              Get started free
            </Link>
            <Link
              href="/demo"
              className="inline-flex h-14 items-center gap-2.5 rounded-full border-2 border-ink bg-white/70 px-6 text-sm font-semibold text-ink transition-transform duration-300 ease-out-expo hover:-translate-y-0.5 hover:bg-white"
            >
              <Play className="size-3.5 fill-current" aria-hidden="true" />
              Explore sample data
            </Link>
          </div>
          {/* Appears once the sign-in options load, so its delay counts from then. */}
          <WhatsAppStart className="rise-in mt-5 text-sm leading-relaxed text-sunflower-ink" style={delay(0.4)} />
          <ul
            className="rise-in mt-10 flex flex-wrap gap-x-6 gap-y-2 text-[13px] font-semibold text-sunflower-ink"
            style={delay(0.85)}
          >
            {assurances.map((item) => (
              <li key={item} className="flex items-center gap-2">
                <ShieldCheck className="size-4 text-ink" aria-hidden="true" />
                {item}
              </li>
            ))}
          </ul>
        </div>
        <div className="rise-in mx-auto w-full max-w-[34rem]" style={delay(0.35)}>
          <MoneyScene className="w-full" />
        </div>
      </div>
      <div
        aria-hidden="true"
        className="rise-in absolute bottom-7 left-1/2 z-[2] hidden -translate-x-1/2 flex-col items-center gap-2 text-[11px] font-semibold tracking-[0.2em] text-sunflower-ink lg:flex"
        style={delay(1.2)}
      >
        SCROLL
        <span className="relative h-10 w-px overflow-hidden bg-ink/15">
          <span className="absolute inset-x-0 top-0 h-1/2 animate-[scroll-cue_2.4s_var(--ease-in-out-quint)_infinite] bg-ink" />
        </span>
      </div>
    </section>
  );
}
