import {
  BadgeIndianRupee,
  CalendarClock,
  CreditCard,
  Landmark,
  ReceiptText,
  ShoppingBag,
  Smartphone,
  Undo2,
} from "lucide-react";

const sources = [
  { label: "Text entries", icon: Landmark },
  { label: "UPI screenshots", icon: Smartphone },
  { label: "Voice notes", icon: CreditCard },
  { label: "Bill photos", icon: ReceiptText },
  { label: "Statement imports", icon: CalendarClock },
  { label: "Income entries", icon: BadgeIndianRupee },
  { label: "Cash purchases", icon: ShoppingBag },
  { label: "Refunds", icon: Undo2 },
] as const;

function Row({ hidden = false }: { hidden?: boolean }) {
  return (
    <ul aria-hidden={hidden || undefined} className="flex shrink-0 items-center gap-3 pr-3">
      {sources.map(({ label, icon: Icon }) => (
        <li
          key={label}
          className="glass flex items-center gap-2.5 rounded-full px-4 py-2.5 text-sm font-semibold whitespace-nowrap text-ink"
        >
          <Icon className="size-4 text-ink" aria-hidden="true" />
          {label}
        </li>
      ))}
    </ul>
  );
}

/** Infinite, edge-faded marquee of the money mail FinBoy understands. */
export function SourcesMarquee() {
  return (
    <section aria-label="Ways to record your money" className="relative overflow-hidden border-y border-white/70 bg-white/40 py-6">
      <div className="mx-auto flex max-w-[1360px] flex-col gap-5 px-6 sm:px-10 md:flex-row md:items-center lg:px-16">
        <p className="shrink-0 text-sm font-semibold text-ink-soft md:w-56">Record money in a way that fits your day</p>
        <div className="flex overflow-hidden [mask-image:linear-gradient(90deg,transparent,#000_10%,#000_90%,transparent)]">
          <div className="flex animate-[marquee_42s_linear_infinite] motion-reduce:animate-none">
            <Row />
            <Row hidden />
          </div>
        </div>
      </div>
    </section>
  );
}
