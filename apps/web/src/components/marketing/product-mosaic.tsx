"use client";

import { ArrowDownLeft, ArrowUpRight, Check, FileText, Sparkles } from "lucide-react";
import { motion, useScroll, useTransform } from "motion/react";
import { useRef, type ReactNode } from "react";

import { cn } from "@/lib/utils";

import { SectionHeading } from "./section-heading";

// Synthetic tiles in the web app's own wording (Home, Transactions, Reports, Ask, Sources).

function Tile({ children, className = "surface" }: { children: ReactNode; className?: string }) {
  return <div className={cn("w-[300px] shrink-0 rounded-[1.6rem] p-5", className)}>{children}</div>;
}

/** Home's money number, on sunflower as in the app. */
function SummaryTile() {
  return (
    <Tile className="solid-hero">
      <p className="text-xs font-semibold text-sunflower-ink">Left this month</p>
      <p className="tabular mt-1 text-3xl font-semibold tracking-[-0.03em]">₹14,780</p>
      <div className="mt-4 h-2 overflow-hidden rounded-full bg-white/55">
        <div className="h-full w-[62%] rounded-full bg-ink" />
      </div>
      <p className="mt-3 text-[11px] text-sunflower-ink">Your actual bank balance may differ.</p>
    </Tile>
  );
}

// The app's record glyphs: money in on green, money out on white.
const OUT = "bg-white/80 text-ink ring-1 ring-ink/[0.06]";

function TransactionsTile() {
  const rows = [
    { name: "Salary · Acme Labs", amount: "+₹62,000", icon: ArrowDownLeft, tone: "text-positive", glyph: "bg-emerald-50 text-positive" },
    { name: "Rent · UPI", amount: "−₹15,000", icon: ArrowUpRight, tone: "text-ink", glyph: OUT },
    { name: "Groceries · milkman", amount: "−₹500", icon: ArrowUpRight, tone: "text-ink", glyph: OUT },
    { name: "Food & dining", amount: "−₹190", icon: ArrowUpRight, tone: "text-ink", glyph: OUT },
  ];
  return (
    <Tile>
      <p className="text-xs font-semibold text-ink-soft">This week</p>
      <ul className="mt-3 space-y-2.5">
        {rows.map(({ name, amount, icon: Icon, tone, glyph }) => (
          <li key={name} className="flex items-center gap-3 text-sm">
            <span className={cn("grid size-8 place-items-center rounded-full", glyph)}>
              <Icon className="size-4" aria-hidden="true" />
            </span>
            <span className="flex-1 text-ink">{name}</span>
            <span className={`tabular font-semibold ${tone}`}>{amount}</span>
          </li>
        ))}
      </ul>
    </Tile>
  );
}

/** FinBoy's ask-first card for a big amount (english.py ASK_BIG and the confirm buttons). */
function CheckFirstTile() {
  return (
    <Tile>
      <p className="text-xs font-semibold text-amber-800">💡 That’s a big amount, so please check it first.</p>
      <p className="mt-2 font-semibold text-ink">💸 ₹52,000 paid · Rent</p>
      <p className="text-xs text-ink-soft">Is this right?</p>
      <div className="mt-4 flex flex-wrap gap-2 text-xs font-semibold">
        <span className="rounded-full bg-ink px-3 py-1.5 text-white">✅ Yes, correct</span>
        <span className="rounded-full bg-white px-3 py-1.5 text-ink ring-1 ring-ink/10">✏️ Change amount</span>
        <span className="rounded-full bg-muted px-3 py-1.5 text-ink-soft">❌ No</span>
      </div>
    </Tile>
  );
}

function AssistantTile() {
  return (
    <Tile>
      <p className="flex items-center gap-1.5 text-xs font-semibold text-ink">
        <Sparkles className="size-3.5" aria-hidden="true" /> FinBoy
      </p>
      <p lang="ml" className="mt-2 text-[0.95rem] leading-relaxed text-ink">
        ഈ മാസം ഇതുവരെ ഭക്ഷണത്തിനായി 7,860 രൂപ ചെലവായിട്ടുണ്ട്.
      </p>
      <p className="mt-3 text-xs text-ink-subtle">12 transactions · Tap for sources</p>
    </Tile>
  );
}

function StatementTile() {
  const steps = ["142 rows read", "Money in and out match Google’s totals", "142 entries saved"];
  return (
    <Tile>
      <p className="flex items-center gap-1.5 text-xs font-semibold text-ink-soft">
        <FileText className="size-3.5" aria-hidden="true" /> Google Pay statement · Sep–Oct
      </p>
      <ul className="mt-3 space-y-1.5 text-sm text-ink">
        {steps.map((step) => (
          <li key={step} className="flex items-center gap-2">
            <Check className="size-3.5 text-positive" aria-hidden="true" />
            {step}
          </li>
        ))}
      </ul>
    </Tile>
  );
}

function BudgetsTile() {
  const rows = [
    { name: "Food & dining", spent: "₹3,600", limit: "₹5,000", share: "72%", mark: "🟢" },
    { name: "Transport", spent: "₹1,700", limit: "₹2,000", share: "85%", mark: "🟡" },
    { name: "Shopping", spent: "₹2,450", limit: "₹2,000", share: "100%", mark: "🔴" },
  ];
  return (
    <Tile>
      <p className="text-xs font-semibold text-ink-soft">Budgets this month</p>
      <ul className="mt-3 space-y-2.5 text-sm text-ink">
        {rows.map((row) => (
          <li key={row.name}>
            <p className="flex justify-between gap-3">
              <span>
                {row.mark} {row.name}
              </span>
              <span className="tabular text-ink-soft">
                {row.spent} of {row.limit}
              </span>
            </p>
            <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-ink/[0.08]">
              <div className="h-full rounded-full bg-ink" style={{ width: row.share }} />
            </div>
          </li>
        ))}
      </ul>
    </Tile>
  );
}

const TILES = [SummaryTile, TransactionsTile, CheckFirstTile, AssistantTile, StatementTile, BudgetsTile];

/** Reference-3 style: a tilted wall of live product cards drifting diagonally as you scroll. */
export function ProductMosaic() {
  const section = useRef<HTMLElement>(null);
  const { scrollYProgress } = useScroll({ target: section, offset: ["start end", "end start"] });
  // Same output on server and client; reduced motion freezes the drift in CSS instead.
  const shiftA = useTransform(scrollYProgress, [0, 1], [120, -220]);
  const shiftB = useTransform(scrollYProgress, [0, 1], [-160, 160]);
  const rows = [0, 1, 2, 3];

  return (
    <section ref={section} aria-labelledby="mosaic-title" className="relative overflow-hidden py-16 sm:py-28">
      <div className="mx-auto max-w-[1360px] px-6 sm:px-10 lg:px-16">
        <SectionHeading
          id="mosaic-title"
          eyebrow="Inside FinBoy"
          align="center"
          title="A calmer way to see your money."
          description="The web app shows the same diary as charts: where the money went, your budgets and what is left this month."
        />
      </div>
      <div aria-hidden="true" className="relative mt-10 h-[440px] [perspective:2200px] sm:mt-14 [mask-image:radial-gradient(ellipse_70%_70%_at_50%_50%,#000_45%,transparent_100%)] sm:h-[640px]">
        <div className="absolute top-1/2 left-1/2 flex [transform-style:preserve-3d] [transform:translate(-50%,-50%)_rotateX(48deg)_rotateZ(-34deg)]">
          <div className="flex flex-col gap-6">
            {rows.map((row) => (
              <motion.div
                key={row}
                className="flex gap-6 motion-reduce:[transform:none!important]"
                style={{ x: row % 2 === 0 ? shiftA : shiftB }}
              >
                {[...TILES, ...TILES].map((TileComponent, index) => (
                  <TileComponent key={`${row}-${index}`} />
                ))}
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
