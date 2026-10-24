"use client";

import { AlertCircle, ArrowDownLeft, ArrowUpRight, Check, Mail, ShieldCheck, Sparkles } from "lucide-react";
import { motion, useScroll, useTransform } from "motion/react";
import { useRef, type ReactNode } from "react";

import { SectionHeading } from "./section-heading";

function Tile({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`surface w-[300px] shrink-0 rounded-[1.6rem] p-5 ${className}`}>{children}</div>;
}

function SummaryTile() {
  return (
    <Tile>
      <p className="text-xs font-semibold text-ink-soft">Estimated unallocated</p>
      <p className="tabular mt-1 text-3xl font-semibold tracking-[-0.03em] text-ink">₹14,780</p>
      <div className="mt-4 h-2 overflow-hidden rounded-full bg-lilac">
        <div className="h-full w-[62%] rounded-full bg-[linear-gradient(90deg,#6d4aff,#d63af9)]" />
      </div>
      <p className="mt-3 text-[11px] text-ink-subtle">Your actual bank balance may differ.</p>
    </Tile>
  );
}

function TransactionsTile() {
  const rows = [
    { name: "Salary · Acme Labs", amount: "+₹62,000", icon: ArrowDownLeft, tone: "text-positive" },
    { name: "Rent · UPI", amount: "−₹15,000", icon: ArrowUpRight, tone: "text-ink" },
    { name: "Swiggy", amount: "−₹842", icon: ArrowUpRight, tone: "text-ink" },
    { name: "Amazon · 3 sources", amount: "−₹799", icon: ArrowUpRight, tone: "text-ink" },
  ];
  return (
    <Tile>
      <p className="text-xs font-semibold text-ink-soft">This week</p>
      <ul className="mt-3 space-y-2.5">
        {rows.map(({ name, amount, icon: Icon, tone }) => (
          <li key={name} className="flex items-center gap-3 text-sm">
            <span className="grid size-8 place-items-center rounded-full bg-lilac text-violet">
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

function ReviewTile() {
  return (
    <Tile>
      <p className="flex items-center gap-1.5 text-xs font-semibold text-amber-800">
        <AlertCircle className="size-3.5" aria-hidden="true" /> Needs your help
      </p>
      <p className="mt-2 font-semibold text-ink">₹1,840 · Possible Amazon order</p>
      <p className="text-xs text-ink-soft">No payment proof found yet</p>
      <div className="mt-4 flex gap-2 text-xs font-semibold">
        <span className="rounded-full bg-ink px-3 py-1.5 text-white">Confirm</span>
        <span className="rounded-full bg-lilac px-3 py-1.5 text-violet">Edit</span>
        <span className="rounded-full bg-muted px-3 py-1.5 text-ink-soft">Not mine</span>
      </div>
    </Tile>
  );
}

function AssistantTile() {
  return (
    <Tile className="bg-[linear-gradient(140deg,#ffffff,#f1f4ff)]">
      <p className="flex items-center gap-1.5 text-xs font-semibold text-violet">
        <Sparkles className="size-3.5" aria-hidden="true" /> FinBoy
      </p>
      <p lang="ml" className="mt-2 text-[0.95rem] leading-relaxed text-ink">
        ഈ മാസം ഇതുവരെ ഭക്ഷണത്തിനായി 7,860 രൂപ ചെലവായിട്ടുണ്ട്.
      </p>
      <p className="mt-3 text-xs text-ink-subtle">12 confirmed transactions · Tap for sources</p>
    </Tile>
  );
}

function ImportTile() {
  const steps = ["126 email headers checked", "38 money emails found", "31 transactions extracted", "4 duplicates merged"];
  return (
    <Tile>
      <p className="flex items-center gap-1.5 text-xs font-semibold text-ink-soft">
        <Mail className="size-3.5" aria-hidden="true" /> Understanding your money…
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

function PrivacyTile() {
  return (
    <Tile>
      <p className="flex items-center gap-1.5 text-xs font-semibold text-ink-soft">
        <ShieldCheck className="size-3.5 text-violet" aria-hidden="true" /> Connected accounts
      </p>
      <p className="mt-2 font-semibold text-ink">arun••••@gmail.com</p>
      <p className="text-xs text-ink-soft">Read-only · Last scan 2 min ago</p>
      <div className="mt-4 flex gap-2 text-xs font-semibold">
        <span className="rounded-full bg-muted px-3 py-1.5 text-ink">Pause</span>
        <span className="rounded-full bg-[#fdecef] px-3 py-1.5 text-negative">Disconnect</span>
      </div>
    </Tile>
  );
}

const TILES = [SummaryTile, TransactionsTile, ReviewTile, AssistantTile, ImportTile, PrivacyTile];

/** Reference-3 style: a tilted wall of live product cards drifting diagonally as you scroll. */
export function ProductMosaic() {
  const section = useRef<HTMLElement>(null);
  const { scrollYProgress } = useScroll({ target: section, offset: ["start end", "end start"] });
  // Same output on server and client; reduced motion freezes the drift in CSS instead.
  const shiftA = useTransform(scrollYProgress, [0, 1], [120, -220]);
  const shiftB = useTransform(scrollYProgress, [0, 1], [-160, 160]);
  const rows = [0, 1, 2, 3];

  return (
    <section ref={section} aria-labelledby="mosaic-title" className="relative overflow-hidden py-24 sm:py-28">
      <div className="mx-auto max-w-[1360px] px-6 sm:px-10 lg:px-16">
        <SectionHeading
          id="mosaic-title"
          eyebrow="Inside FinBoy"
          align="center"
          title="A calmer way to see your money."
          description="Every number shows where it came from. Every guess waits for you."
        />
      </div>
      <div aria-hidden="true" className="relative mt-14 h-[560px] [perspective:2200px] [mask-image:radial-gradient(ellipse_70%_70%_at_50%_50%,#000_45%,transparent_100%)] sm:h-[640px]">
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
