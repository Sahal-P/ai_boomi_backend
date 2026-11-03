import { ChevronsRight, Play, ShieldCheck } from "lucide-react";
import Link from "next/link";

import { MoneyScene } from "@/components/illustrations/scenes";
import { WhatsAppStart } from "@/components/marketing/whatsapp-start";

const lines = ["Your money,", "made easier", "to track."] as const;
const assurances = ["WhatsApp and web", "English, Hindi and Malayalam", "Review and undo"] as const;

/** The landing hero is a yellow moment: flat sunflower, ink and the drawn money scene. */
export function Hero() {
  return (
    <section data-hero aria-labelledby="hero-title" className="moment relative isolate overflow-hidden">
      <div className="relative mx-auto grid min-h-[100svh] max-w-[1360px] content-center items-center gap-x-12 gap-y-10 px-6 pt-28 pb-20 sm:px-10 md:pt-24 lg:grid-cols-[1.05fr_1fr] lg:px-16">
        <div>
          <p
            className="eyebrow inline-flex w-fit items-center gap-2 rounded-full border-2 border-ink bg-white px-3.5 py-1.5 text-ink"
          >
            <span className="size-1.5 rounded-full bg-ink" />
            AI expense tracker for India
          </p>
          <h1
            id="hero-title"
            className="mt-7 max-w-[13ch] text-[clamp(2.85rem,6.4vw,5.6rem)] leading-[1.0] font-extrabold tracking-[-0.05em] text-ink"
          >
            {lines.map((line) => (
              <span key={line} className="line-mask">
                <span>
                  {line}
                </span>{" "}
              </span>
            ))}
          </h1>
          <p
            className="mt-7 max-w-[30rem] text-[1.0625rem] leading-relaxed text-sunflower-ink"
          >
            Track everyday spending on WhatsApp or the web. Add expenses by voice, share UPI
            screenshots and import supported Google Pay statements.
          </p>
          <div className="mt-9 flex flex-wrap items-center gap-3">
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
          <WhatsAppStart className="mt-5 text-sm leading-relaxed text-sunflower-ink" />
          <ul
            className="mt-10 flex flex-wrap gap-x-6 gap-y-2 text-[13px] font-semibold text-sunflower-ink"
          >
            {assurances.map((item) => (
              <li key={item} className="flex items-center gap-2">
                <ShieldCheck className="size-4 text-ink" aria-hidden="true" />
                {item}
              </li>
            ))}
          </ul>
        </div>
        <div className="mx-auto w-full max-w-[34rem]">
          <MoneyScene className="w-full" />
        </div>
      </div>
      <div
        aria-hidden="true"
        className="absolute bottom-7 left-1/2 z-[2] hidden -translate-x-1/2 flex-col items-center gap-2 text-[11px] font-semibold tracking-[0.2em] text-sunflower-ink lg:flex"
      >
        SCROLL
        <span className="relative h-10 w-px overflow-hidden bg-ink/15">
          <span className="absolute inset-x-0 top-0 h-1/2 animate-[scroll-cue_2.4s_var(--ease-in-out-quint)_infinite] bg-ink" />
        </span>
      </div>
    </section>
  );
}
