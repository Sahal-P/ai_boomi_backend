"use client";

import { useId } from "react";
import { count, moment, Panel } from "@/components/admin/admin-bits";
import { SOURCE_DAYS, type Journey, type SourceDays, type SourceRow } from "@/lib/api/admin";
import { sourceLabel, span } from "@/lib/signup-sources";

const STEPS = [
  ["opened", "Opened"],
  ["tapped", "Tapped WhatsApp"],
  ["signed_up", "Signed up"],
  ["agreed", "Agreed"],
  ["first_record", "First record"],
] as const;
const TIMES = [
  ["minutes_to_tap", "Open → tap"],
  ["minutes_to_sign_up", "Tap → first message"],
  ["minutes_to_record", "First message → first record"],
] as const;

/**
 * Where sign-ups came from (docs/ad-journey-round/contract.md): for each link's tags, how many
 * opened a page, tapped WhatsApp, signed up, agreed and made a first record, and the median time
 * between. Counts and times only.
 */
export function SignupSources({
  rows,
  days,
  onDays,
  busy,
}: {
  rows: SourceRow[];
  days: SourceDays;
  onDays: (days: SourceDays) => void;
  busy: boolean;
}) {
  const ids = useId();
  return (
    <Panel
      title="Where sign-ups came from"
      description="Each link's utm tags, from page to first record. Instagram tags its own bio links ig · social; our ads say paid_social."
    >
      <div className="max-w-xs">
        <label htmlFor={`${ids}-days`} className="text-xs font-semibold">
          Period
        </label>
        <select
          id={`${ids}-days`}
          className="field field-select mt-1.5 block h-11 w-full rounded-lg pl-3 text-sm"
          value={days}
          disabled={busy}
          onChange={(event) => onDays(Number(event.target.value) as SourceDays)}
        >
          {SOURCE_DAYS.map((value) => (
            <option key={value} value={value}>
              Last {value} days
            </option>
          ))}
        </select>
      </div>
      {rows.length === 0 ? (
        <p className="mt-4 text-sm text-ink-soft">No visits or sign-ups in this period.</p>
      ) : (
        <>
          <table className="mt-4 hidden w-full text-sm lg:table">
            <caption className="sr-only">Sign-ups by source, last {days} days</caption>
            <thead>
              <tr className="text-left text-xs text-ink-soft">
                <th scope="col" className="py-2 pr-3 font-semibold">
                  Source
                </th>
                {STEPS.map(([key, title]) => (
                  <th key={key} scope="col" className="px-2 py-2 text-right font-semibold">
                    {title}
                  </th>
                ))}
                {TIMES.map(([key, title]) => (
                  <th key={key} scope="col" className="px-2 py-2 text-right font-semibold">
                    {title}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-ink/[0.07]">
              {rows.map((row) => (
                <tr key={sourceLabel(row)}>
                  <th scope="row" className="py-2 pr-3 text-left font-medium break-words">
                    {sourceLabel(row)}
                  </th>
                  {STEPS.map(([key]) => (
                    <td key={key} className="px-2 py-2 text-right font-semibold tabular-nums">
                      {row.direct && (key === "opened" || key === "tapped") ? "—" : count(row[key])}
                    </td>
                  ))}
                  {TIMES.map(([key]) => (
                    <td key={key} className="px-2 py-2 text-right tabular-nums">
                      {span(row[key])}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          <ul className="mt-4 space-y-3 lg:hidden">
            {rows.map((row) => (
              <li key={sourceLabel(row)} className="rounded-xl bg-ink/[0.035] p-4">
                <p className="font-semibold break-words">{sourceLabel(row)}</p>
                <dl className="mt-2 grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-1 text-sm">
                  {STEPS.filter(([key]) => !(row.direct && (key === "opened" || key === "tapped"))).map(
                    ([key, title]) => (
                      <div key={key} className="contents">
                        <dt className="text-ink-soft">{title}</dt>
                        <dd className="text-right font-semibold tabular-nums">{count(row[key])}</dd>
                      </div>
                    ),
                  )}
                  {TIMES.map(([key, title]) => (
                    <div key={key} className="contents">
                      <dt className="text-ink-soft">{title}</dt>
                      <dd className="text-right tabular-nums">{span(row[key])}</dd>
                    </div>
                  ))}
                </dl>
              </li>
            ))}
          </ul>
        </>
      )}
    </Panel>
  );
}

const BROWSERS = { instagram: "Instagram's browser", facebook: "Facebook's browser", other: "Another browser" };
const PLATFORMS = { android: "Android", ios: "iPhone or iPad", desktop: "Computer", other: "Other" };

/** One household's way in, for its detail page. */
export function journeyFacts(journey: Journey): [string, string][] {
  const visited = journey.opened !== null;
  return [
    ["Came from", visited ? sourceLabel({ ...journey, direct: false }) : "No page visit"],
    ...(visited
      ? ([
          ["Page", journey.landing ?? "—"],
          [
            "Opened on",
            [journey.browser && BROWSERS[journey.browser], journey.platform && PLATFORMS[journey.platform]]
              .filter(Boolean)
              .join(" · ") || "—",
          ],
          ["Page opened", moment(journey.opened)],
          ["Tapped WhatsApp", moment(journey.tapped)],
        ] satisfies [string, string][])
      : []),
    ["First message", moment(journey.first_message)],
    ["Agreed", moment(journey.agreed)],
    ["WhatsApp linked", moment(journey.whatsapp_linked)],
    ["First record", moment(journey.first_record)],
  ];
}
