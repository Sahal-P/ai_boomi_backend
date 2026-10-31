import Link from "next/link";
import type { ReactNode } from "react";
import { formatMoney, periodSearch, type Insights, type PayeeTotal, type Period } from "@/lib/api/money";
import { sharePercent } from "@/lib/charts";
import { formatDay } from "@/lib/dates";
import { categoryLabels } from "@/lib/labels";
import { cn } from "@/lib/utils";

const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`;

/** Records of one payee (a merchant search) in the period, or across all time. */
function payeeHref(name: string, period: Period | "all", status = "") {
  const scope = period === "all" ? "&scope=all" : periodSearch(period);
  return `/transactions?q=${encodeURIComponent(name)}${status}${scope}`;
}

function Section({ id, title, note, children }: { id: string; title: string; note?: ReactNode; children: ReactNode }) {
  return (
    <section aria-labelledby={id} className="surface min-w-0 rounded-3xl p-5 sm:p-6">
      <h2 id={id} className="text-lg font-semibold">
        {title}
      </h2>
      {note && <p className="mt-1 text-xs leading-relaxed text-ink-soft">{note}</p>}
      {children}
    </section>
  );
}

/** Payees as a table with a bar for each amount; a name opens that payee's records. */
function PayeeTable({
  caption,
  items,
  period,
  bar,
}: {
  caption: string;
  items: PayeeTotal[];
  period: Period;
  bar: "bg-chart-out" | "bg-chart-in";
}) {
  const largest = items[0]?.amount_minor ?? 0;
  return (
    <table className="mt-3 w-full table-fixed text-sm">
      <caption className="sr-only">{caption}</caption>
      <thead className="sr-only">
        <tr>
          <th scope="col">Name</th>
          <th scope="col">Amount</th>
          <th scope="col">Payments</th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item.name}>
            <td className="py-1.5 pr-3 align-top">
              {/* Names wrap to two lines: on a phone the figures leave them little room. */}
              <Link
                href={payeeHref(item.name, period, "&status=confirmed")}
                className="line-clamp-2 font-medium break-words underline-offset-4 hover:underline"
              >
                {item.name}
              </Link>
              <span aria-hidden="true" className="mt-1.5 block h-1.5 overflow-hidden rounded-full bg-ink/[0.06]">
                <span
                  className={cn("block h-full rounded-full", bar)}
                  style={{ width: `${largest ? Math.max(2, (item.amount_minor / largest) * 100) : 0}%` }}
                />
              </span>
            </td>
            <td className="w-24 py-1.5 text-right align-top font-semibold tabular-nums sm:w-28">{formatMoney(item.amount_minor)}</td>
            <td className="w-16 py-1.5 pl-2 text-right align-top text-xs text-ink-soft tabular-nums sm:w-[4.5rem]">
              {sharePercent(item.share)}
              <span className="block">{plural(item.count, "time", "times")}</span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Top payees, who pays you and the biggest payments of the period. */
export function WhoYouPay({ insights, period, label }: { insights: Insights; period: Period; label: string }) {
  if (!insights.top_payees.length && !insights.top_senders.length) return null;
  return (
    <Section
      id="payees-title"
      title="Who you pay most"
      note={`Confirmed payments in ${label}, by amount. Tap a name for every payment.`}
    >
      {insights.top_payees.length > 0 && (
        <PayeeTable caption="Who you paid most" items={insights.top_payees} period={period} bar="bg-chart-out" />
      )}
      {insights.top_senders.length > 0 && (
        <>
          <h3 className="mt-6 text-sm font-semibold">Who pays you</h3>
          <PayeeTable caption="Who paid you most" items={insights.top_senders} period={period} bar="bg-chart-in" />
        </>
      )}
      {insights.biggest.length > 0 && (
        <>
          <h3 className="mt-6 text-sm font-semibold">Biggest payments</h3>
          <ul className="mt-2 divide-y">
            {insights.biggest.map((item) => (
              <li key={item.id}>
                <Link
                  href={`/transactions?selected=${item.id}${periodSearch(period)}`}
                  className="flex min-h-11 items-center gap-3 py-2 text-sm hover:bg-white/50"
                >
                  <span className="min-w-0 flex-1">
                    <span className="line-clamp-2 font-medium break-words">{item.name}</span>
                    <span className="block text-xs text-ink-soft">
                      {formatDay(item.occurred_at)} · {categoryLabels[item.category]}
                    </span>
                  </span>
                  <span className="font-semibold tabular-nums">{formatMoney(item.amount_minor)}</span>
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}
    </Section>
  );
}

/** Bills and subscriptions paid a steady amount month after month. */
export function RegularPayments({ insights }: { insights: Insights }) {
  if (!insights.regular.length) return null;
  return (
    <Section
      id="regular-title"
      title="Regular payments"
      note="Paid a steady amount in at least 3 of the last 6 months — subscriptions, bills, recharges and the like."
    >
      <p className="mt-3 text-2xl font-semibold tracking-[-0.02em] tabular-nums">
        About {formatMoney(insights.regular_monthly_minor)}
        <span className="text-sm font-medium tracking-normal text-ink-soft"> a month</span>
      </p>
      <ul className="mt-3 divide-y">
        {insights.regular.map((item) => (
          <li key={item.name}>
            <Link href={payeeHref(item.name, "all")} className="flex min-h-11 items-center gap-3 py-2 text-sm hover:bg-white/50">
              <span className="min-w-0 flex-1">
                <span className="line-clamp-2 font-medium break-words">{item.name}</span>
                <span className="block text-xs text-ink-soft">
                  {categoryLabels[item.category]} · {item.months} of the last 6 months · next around {formatDay(item.next_expected)}
                </span>
              </span>
              <span className="font-semibold tabular-nums">{formatMoney(item.usual_minor)}</span>
            </Link>
          </li>
        ))}
      </ul>
    </Section>
  );
}

function balanceLine(balance: number) {
  if (balance === 0) return "Even";
  return balance > 0 ? `${formatMoney(balance)} more came back` : `You sent ${formatMoney(-balance)} more`;
}

/** People money went to and came back from: shared costs, loans, family. */
export function MoneyWithPeople({ insights, period, label }: { insights: Insights; period: Period; label: string }) {
  if (!insights.people.length) return null;
  return (
    <Section id="people-title" title="Money with people" note={`Everyone you both paid and received money from in ${label}.`}>
      <ul className="mt-3 divide-y">
        {insights.people.map((person) => (
          <li key={person.name}>
            <Link href={payeeHref(person.name, period)} className="flex min-h-11 items-center gap-3 py-2 text-sm hover:bg-white/50">
              <span className="min-w-0 flex-1">
                <span className="line-clamp-2 font-medium break-words">{person.name}</span>
                <span className="block text-xs text-ink-soft tabular-nums">
                  Sent {formatMoney(person.sent_minor)} · got back {formatMoney(person.received_minor)}
                </span>
              </span>
              <span
                className={cn(
                  "shrink-0 text-right text-xs font-semibold",
                  person.balance_minor > 0 ? "text-positive" : person.balance_minor < 0 ? "text-ink" : "text-ink-soft",
                )}
              >
                {balanceLine(person.balance_minor)}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </Section>
  );
}

/** What payments under ₹200 add up to, and where they go. */
export function SmallPayments({ insights, period }: { insights: Insights; period: Period }) {
  const small = insights.small;
  if (!small.count) return null;
  const threshold = formatMoney(small.threshold_minor);
  return (
    <Section id="small-title" title="Small payments">
      <p className="mt-3 text-2xl font-semibold tracking-[-0.02em] tabular-nums">
        {formatMoney(insights.months > 1 ? small.per_month_minor : small.amount_minor)}
        <span className="text-sm font-medium tracking-normal text-ink-soft">
          {insights.months > 1 ? " a month" : " this month"} under {threshold}
        </span>
      </p>
      <p className="mt-1 text-sm text-ink-soft">
        {plural(small.count, "payment", "payments")} — {sharePercent(small.count_share)} of your payments but{" "}
        {sharePercent(small.amount_share)} of your money.
      </p>
      {small.places.length > 0 && (
        <>
          <h3 className="mt-4 text-sm font-semibold">Most often at</h3>
          <ul className="mt-1 divide-y">
            {small.places.map((place) => (
              <li key={place.name}>
                <Link
                  href={payeeHref(place.name, period, "&status=confirmed")}
                  className="flex min-h-11 items-center gap-3 py-2 text-sm hover:bg-white/50"
                >
                  <span className="line-clamp-2 min-w-0 flex-1 font-medium break-words">{place.name}</span>
                  <span className="text-xs text-ink-soft tabular-nums">
                    {plural(place.count, "time", "times")} · {formatMoney(place.amount_minor)}
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}
    </Section>
  );
}
