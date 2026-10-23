import {
  ArrowDownRight,
  ArrowRight,
  Asterisk,
  Compass,
  Fingerprint,
  IndianRupee,
  Sparkles,
} from "lucide-react";
import { Brand } from "@/components/brand";
import { ConnectionStatus } from "@/components/connection-status";

const principles = [
  {
    number: "01",
    icon: IndianRupee,
    title: "India, at heart.",
    description:
      "Built around the way we live, think, and talk about money in India.",
  },
  {
    number: "02",
    icon: Compass,
    title: "Clarity, by design.",
    description:
      "A calmer perspective on personal finance. Less noise, more understanding.",
  },
  {
    number: "03",
    icon: Fingerprint,
    title: "Privacy, from day one.",
    description:
      "A thoughtful foundation, with care for your information at every step.",
  },
];

export default function Home() {
  return (
    <div className="mx-auto max-w-[1280px] px-6 sm:px-10 lg:px-16">
      <a
        href="#main"
        className="sr-only rounded-md bg-foreground px-4 py-3 text-background focus:not-sr-only focus:absolute focus:top-4 focus:z-50"
      >
        Skip to content
      </a>
      <header className="flex h-24 items-center justify-between gap-5 border-b">
        <Brand />
        <nav
          aria-label="Main navigation"
          className="hidden items-center gap-8 text-sm text-muted-foreground sm:flex"
        >
          <a
            href="#approach"
            className="transition-colors hover:text-foreground"
          >
            Our approach
          </a>
          <a
            href="#foundation"
            className="transition-colors hover:text-foreground"
          >
            The foundation
          </a>
        </nav>
        <span className="inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-[11px] font-medium tracking-wide">
          <span
            className="size-1.5 rounded-full bg-primary"
            aria-hidden="true"
          />
          EARLY PREVIEW
        </span>
      </header>
      <main id="main">
        <section
          aria-labelledby="hero-title"
          className="grid items-center gap-12 pb-14 pt-14 sm:pt-20 lg:min-h-[650px] lg:grid-cols-[1.08fr_1fr] lg:gap-10 lg:py-20"
        >
          <div>
            <p className="eyebrow mb-7 flex items-center gap-2.5 text-primary">
              <span className="h-px w-6 bg-primary" aria-hidden="true" />A FRESH
              PERSPECTIVE ON PERSONAL FINANCE
            </p>
            <h1
              id="hero-title"
              className="max-w-xl text-[clamp(3.2rem,6.2vw,5.25rem)] leading-[1.055] font-medium tracking-[-0.065em]"
            >
              Your money,
              <br />
              with a little
              <br />
              <span className="text-primary">more clarity.</span>
            </h1>
            <p className="mt-7 max-w-[24rem] text-[15px] leading-[1.8] text-muted-foreground sm:text-base">
              Meet FinBoy. An AI-powered personal finance copilot, thoughtfully
              built for India. A little less overwhelm. A little more
              perspective.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-5 sm:gap-7">
              <a
                href="#approach"
                className="inline-flex h-12 items-center gap-6 rounded-xl bg-primary px-5 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
              >
                Explore FinBoy{" "}
                <ArrowRight className="size-4" aria-hidden="true" />
              </a>
              <a
                href="#foundation"
                className="inline-flex items-center gap-2 text-sm font-medium transition-colors hover:text-primary"
              >
                See what’s live{" "}
                <ArrowDownRight className="size-4" aria-hidden="true" />
              </a>
            </div>
            <p className="mt-6 text-xs text-muted-foreground">
              A small beginning. A more thoughtful money journey.
            </p>
          </div>
          <div
            aria-hidden="true"
            className="clarity-art relative mx-auto h-[410px] w-full max-w-[430px] sm:h-[465px]"
          >
            <div className="art-orbit absolute inset-x-1 top-10 h-[330px] rounded-[50%] border border-primary/15 sm:top-14 sm:h-[350px]" />
            <div className="absolute inset-x-10 top-14 bottom-10 rotate-[8deg] rounded-[20px] bg-[#dfece3]" />
            <div className="clarity-paper absolute inset-x-6 top-5 bottom-16 flex -rotate-[5deg] flex-col rounded-[18px] border border-[#d8ded5] bg-[#fffefa] p-7 sm:inset-x-10 sm:p-8">
              <div className="flex items-center justify-between text-[9px] font-medium tracking-[0.18em] text-muted-foreground">
                <span>FINBOY / A NEW PERSPECTIVE</span>
                <span>001</span>
              </div>
              <span className="mt-5 flex size-14 shrink-0 items-center justify-center rounded-full bg-primary text-[#e0efcc] sm:mt-6 sm:size-16">
                <IndianRupee className="size-8 sm:size-9" strokeWidth={1.5} />
              </span>
              <p className="mt-5 text-[clamp(1.75rem,8.8vw,2.15rem)] leading-[1.08] font-medium tracking-[-0.055em] sm:text-[2.5rem]">
                Good things
                <br />
                start with
                <br />
                <span className="text-primary">clarity.</span>
              </p>
              <div className="mt-auto flex items-center justify-between border-t pt-4 text-[9px] tracking-[0.12em] text-muted-foreground">
                <span>MADE FOR INDIA</span>
                <Asterisk className="size-4 text-primary" />
              </div>
            </div>
            <span className="absolute right-0 bottom-4 flex rotate-[3deg] items-center gap-3 rounded-xl border bg-card px-5 py-4 text-xs shadow-[0_8px_25px_-18px_#233e2f55] sm:bottom-12">
              <Sparkles className="size-4 text-primary" strokeWidth={1.5} />
              Money, meet peace of mind.
            </span>
            <span className="absolute top-0 right-3 flex size-9 items-center justify-center rounded-full border border-primary/20 text-primary">
              <Asterisk className="size-5" />
            </span>
          </div>
        </section>
        <section
          id="approach"
          aria-label="The FinBoy approach"
          className="grid scroll-mt-8 gap-8 border-t py-10 sm:grid-cols-3 sm:gap-7 lg:gap-12 lg:py-12"
        >
          {principles.map(({ number, icon: Icon, title, description }) => (
            <article key={number}>
              <div className="mb-5 flex items-center justify-between">
                <Icon
                  className="size-5 text-primary"
                  strokeWidth={1.5}
                  aria-hidden="true"
                />
                <span className="font-mono text-[10px] text-muted-foreground">
                  /{number}
                </span>
              </div>
              <h2 className="text-base font-medium tracking-tight">{title}</h2>
              <p className="mt-2 max-w-xs text-sm leading-relaxed text-muted-foreground">
                {description}
              </p>
            </article>
          ))}
        </section>
        <ConnectionStatus />
      </main>
      <footer className="flex flex-col justify-between gap-4 py-8 text-[11px] text-muted-foreground sm:flex-row sm:items-center">
        <p>© {new Date().getFullYear()} FinBoy. A little more clarity.</p>
        <p className="flex items-center gap-2">
          <span className="size-1 rounded-full bg-primary" aria-hidden="true" />
          Thoughtfully built for India.
        </p>
      </footer>
    </div>
  );
}
