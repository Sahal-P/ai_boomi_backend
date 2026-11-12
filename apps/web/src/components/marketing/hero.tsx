import { Check, ChevronsRight, Play } from "lucide-react";
import Link from "next/link";

import { MoneyScene } from "@/components/illustrations/scenes";
import { StartLink } from "@/components/marketing/start-link";
import { PREMIUM_PRICE } from "@/lib/business";
import { TRIAL_DAYS } from "@/lib/pricing";

const lines = ["Keep track", "of your money", "on WhatsApp."] as const;
const assurances = ["No app to install", "No bank login or SMS access", "Undo on every saved entry"] as const;

/** The landing hero is a yellow moment: flat sunflower, ink and the drawn money scene. */
export function Hero() {
  return (
    <section data-hero aria-labelledby="hero-title" className="moment relative isolate overflow-hidden">
      <div className="relative mx-auto grid min-h-[100svh] max-w-[1360px] content-center items-center gap-x-12 gap-y-10 px-6 pt-28 pb-20 sm:px-10 md:pt-24 lg:grid-cols-[1.05fr_1fr] lg:px-16">
        <div>
          <p className="eyebrow inline-flex w-fit items-center gap-2 rounded-full border-2 border-ink bg-white px-3.5 py-1.5 text-ink">
            <span className="size-1.5 rounded-full bg-ink" />
            Expense diary on WhatsApp
          </p>
          {/* Below 360 px the longest line ("on WhatsApp.", 6.45 em) needs the smaller size to stay whole. */}
          <h1
            id="hero-title"
            className="mt-7 max-w-[13ch] text-[2.5rem] leading-[1.0] font-extrabold tracking-[-0.05em] text-ink min-[360px]:text-[clamp(2.85rem,6.4vw,5.6rem)]"
          >
            {lines.map((line) => (
              <span key={line} className="line-mask">
                <span>{line}</span>{" "}
              </span>
            ))}
          </h1>
          <p className="mt-7 max-w-[30rem] text-[1.0625rem] leading-relaxed text-sunflower-ink">
            Send “chai 20, auto 50” the way you’d text a friend. FinBoy saves each entry, sorts it
            into a category and replies with Undo in case anything is wrong.
          </p>
          <p className="mt-3 text-sm font-semibold text-ink">
            <span lang="en">English</span> · <span lang="hi">हिंदी</span> · <span lang="ml">മലയാളം</span>
          </p>
          <div className="mt-8 flex flex-wrap items-center gap-3">
            <StartLink
              className="group lg-prominent inline-flex h-14 items-center gap-3 rounded-full p-1 pr-7 text-sm font-semibold hover:-translate-y-0.5"
              before={
                // The reference's chevron capsule, as decoration on an ordinary link: a glass knob.
                <span className="lg-knob grid h-12 w-16 place-items-center rounded-full text-ink transition-transform duration-300 ease-out-expo group-hover:translate-x-0.5">
                  <ChevronsRight className="size-5" aria-hidden="true" />
                </span>
              }
            />
            <Link
              href="/demo"
              className="lg-on-color inline-flex h-14 items-center gap-2.5 rounded-full bg-white/70 px-6 text-sm font-semibold text-ink hover:-translate-y-0.5 hover:bg-white/85"
            >
              <Play className="size-3.5 fill-current" aria-hidden="true" />
              See a sample account
            </Link>
          </div>
          <p className="mt-5 max-w-[30rem] text-sm leading-relaxed text-sunflower-ink">
            Free to start. Voice and photo reading are Premium: {PREMIUM_PRICE} a month after{" "}
            {TRIAL_DAYS} free days. No card needed.
          </p>
          <ul className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-[13px] font-semibold text-sunflower-ink">
            {assurances.map((item) => (
              <li key={item} className="flex items-center gap-2">
                <Check className="size-4 text-ink" aria-hidden="true" />
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
