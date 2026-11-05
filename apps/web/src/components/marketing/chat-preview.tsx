import { Mic } from "lucide-react";
import type { ReactNode } from "react";

import { BrandMark } from "@/components/brand";
import { PremiumPill } from "@/components/billing/premium-pill";

/**
 * A synthetic WhatsApp thread with FinBoy's real reply formats
 * (apps/api/src/finboy/services/whatsapp/english.py: saved_many, saved, budget_line and the
 * button titles). Decoration for sighted readers and plain text for screen readers.
 */

function Glyph({ children }: { children: string }) {
  return <span aria-hidden="true">{children} </span>;
}

function Buttons({ items }: { items: readonly (readonly [string, string])[] }) {
  return (
    <p className="mt-2.5 flex flex-wrap gap-1.5">
      <span className="sr-only">Buttons: </span>
      {items.map(([glyph, label], index) => (
        <span
          key={label}
          className="rounded-full bg-white px-2.5 py-1 text-xs font-semibold text-ink ring-1 ring-ink/10"
        >
          <Glyph>{glyph}</Glyph>
          {label}
          {index < items.length - 1 ? <span className="sr-only">,</span> : null}
        </span>
      ))}
    </p>
  );
}

function You({ children }: { children: ReactNode }) {
  return (
    <li className="flex justify-end">
      <div className="max-w-[85%] rounded-[1.25rem] rounded-br-md bg-ink px-4 py-2.5 text-[0.95rem] text-white">
        <span className="sr-only">You: </span>
        {children}
      </div>
    </li>
  );
}

function FinBoy({ children }: { children: ReactNode }) {
  return (
    <li className="flex justify-start">
      <div className="max-w-[90%] rounded-[1.25rem] rounded-bl-md bg-white/85 px-4 py-3 text-[0.95rem] leading-relaxed text-ink ring-1 ring-ink/5">
        <span className="sr-only">FinBoy: </span>
        {children}
      </div>
    </li>
  );
}

export function ChatPreview() {
  return (
    <figure className="surface mx-auto w-full max-w-md rounded-[2rem] p-4 sm:p-5">
      <div className="flex items-center gap-3 border-b border-ink/10 px-1 pb-3">
        <BrandMark className="size-9" />
        <div>
          <p className="font-semibold text-ink">FinBoy</p>
          <p className="text-xs text-ink-soft">Your diary on WhatsApp</p>
        </div>
      </div>
      <ol className="mt-4 space-y-3" aria-label="Example chat with FinBoy">
        <You>chai 20, auto 50, lunch 120</You>
        <FinBoy>
          <p className="font-semibold">
            <Glyph>✅</Glyph>Saved 3 · ₹190
          </p>
          <p>• ₹20 · Food &amp; dining</p>
          <p>• ₹50 · Transport</p>
          <p>• ₹120 · Food &amp; dining</p>
          <Buttons
            items={[
              ["↩️", "Undo all"],
              ["✏️", "Fix one"],
            ]}
          />
        </FinBoy>
        <You>
          <span className="flex items-center gap-2">
            <Mic className="size-4 opacity-80" aria-hidden="true" />
            <span>Voice note · “Paid the milkman 500”</span>
          </span>
          <PremiumPill className="mt-2" />
        </You>
        <FinBoy>
          <p className="font-semibold">
            <Glyph>✅</Glyph>Saved: ₹500 paid
          </p>
          <p>
            <Glyph>🏷️</Glyph>Groceries
          </p>
          <p>
            <Glyph>👤</Glyph>milkman
          </p>
          <p>
            <Glyph>📅</Glyph>Today
          </p>
          <p>
            <Glyph>🟢</Glyph>Groceries: ₹2,300 of ₹6,000 this month
          </p>
          <Buttons
            items={[
              ["↩️", "Undo"],
              ["✏️", "Amount"],
              ["🏷️", "Category"],
            ]}
          />
        </FinBoy>
      </ol>
      <figcaption className="mt-4 px-1 text-xs leading-relaxed text-ink-soft">
        Synthetic example. The replies and buttons are the ones FinBoy sends.
      </figcaption>
    </figure>
  );
}
