"use client";

import {
  ArrowDownLeft,
  CalendarClock,
  CalendarDays,
  ChevronRight,
  Gauge,
  MessageCircle,
  PiggyBank,
  Repeat,
  Sparkles,
  TriangleAlert,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { useHouseholdAccess } from "@/components/app-shell/household-context";
import { useResource } from "@/hooks/use-resource";
import { chatLink } from "@/lib/api/auth";
import { askLink, getForYou, type ForYouItem, type NudgeKind } from "@/lib/api/coach";
import { cn } from "@/lib/utils";

const ICONS: Record<NudgeKind, LucideIcon> = {
  weekly_recap: CalendarDays,
  due_soon: CalendarClock,
  budget_over: Gauge,
  unusual_payment: TriangleAlert,
  income_in: ArrowDownLeft,
  budget_near: Gauge,
  goal_progress: PiggyBank,
  new_regular: Repeat,
};

// Where each kind is looked at in FinBoy.
const PLACES: Record<NudgeKind, string> = {
  weekly_recap: "See reports",
  due_soon: "See bills",
  budget_over: "See budgets",
  unusual_payment: "Open the payment",
  income_in: "Open the record",
  budget_near: "See budgets",
  goal_progress: "See your goal",
  new_regular: "See regular payments",
};

// The icon's chip only: the words stay ink on the card for contrast.
const TONES = {
  warning: "bg-amber-50 text-amber-800",
  good: "bg-positive/10 text-positive",
  info: "bg-ink/[0.06] text-ink",
} as const;

const action =
  "inline-flex min-h-11 items-center gap-1.5 text-sm font-semibold underline-offset-4 hover:underline";

function Item({ item }: { item: ForYouItem }) {
  const Icon = ICONS[item.kind];
  return (
    <li className="flex gap-3 pt-3.5 pb-1.5">
      <span className={cn("mt-0.5 grid size-9 shrink-0 place-items-center rounded-full", TONES[item.tone])} aria-hidden="true">
        <Icon className="size-4" />
      </span>
      <div className="min-w-0 flex-1">
        <h3 className="text-sm font-semibold">{item.title}</h3>
        <p className="mt-0.5 text-sm leading-relaxed break-words text-ink-soft">{item.text}</p>
        <div className="flex flex-wrap gap-x-5">
          <Link href={item.href} className={action}>
            {PLACES[item.kind]}
            <ChevronRight className="size-4" aria-hidden="true" />
          </Link>
          <Link href={askLink(item.ask)} className={action} aria-label={`Ask FinBoy: ${item.ask}`}>
            <MessageCircle className="size-4" aria-hidden="true" />
            Ask FinBoy
          </Link>
        </div>
      </div>
    </li>
  );
}

/**
 * What FinBoy's coach found today, from the same checks as its WhatsApp nudges: written by code
 * from the household's records, with the place to look and a question for Ask. Secondary to the
 * month, so it stays hidden while loading, on an error and when there is nothing to say.
 */
export function ForYouCard({ version }: { version: number }) {
  const { signIn } = useHouseholdAccess();
  // The last result stays while a refresh after new records is on its way.
  const coach = useResource(`for-you:${version}`, (signal) => getForYou(signal));
  const data = coach.data;
  if (!data?.items.length) return null;
  return (
    <section aria-labelledby="for-you-title" className="surface rounded-3xl p-5 sm:p-6">
      <div className="flex items-center gap-2">
        <Sparkles className="size-4 shrink-0 text-ink-soft" aria-hidden="true" />
        <h2 id="for-you-title" className="text-lg font-semibold">
          For you
        </h2>
      </div>
      <ul className="divide-y">
        {data.items.map((item, index) => (
          <Item key={`${item.kind}-${index}`} item={item} />
        ))}
      </ul>
      {data.whatsapp === "on" && (
        <p className="mt-2 text-xs leading-relaxed text-ink-soft">
          You get these on WhatsApp too, one a day at most. Send &ldquo;coach off&rdquo; there to stop.
        </p>
      )}
      {data.whatsapp === "off" && signIn?.whatsapp_number && (
        <a
          href={chatLink(signIn.whatsapp_number, "coach on")}
          target="_blank"
          rel="noopener noreferrer"
          className={cn(action, "mt-1 text-ink-soft hover:text-ink")}
        >
          <MessageCircle className="size-4" aria-hidden="true" />
          Get one a day on WhatsApp
        </a>
      )}
    </section>
  );
}
