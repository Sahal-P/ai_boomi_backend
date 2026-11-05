"use client";

import { useEffect, useRef, type ReactNode } from "react";
import { CountTable, count, day, Facts, Meter, moment } from "@/components/admin/admin-bits";
import { HouseholdActions } from "@/components/admin/household-actions";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { LoadingPanel, RefreshingLabel } from "@/components/feedback/states";
import { Badge } from "@/components/ui/badge";
import { useResource } from "@/hooks/use-resource";
import {
  dueLabels,
  importModeLabels,
  kindLabels,
  label,
  languageLabels,
  paymentStatusLabels,
  planLabels,
  readable,
  recordLabels,
  statusLabels,
} from "@/lib/admin-labels";
import { getHousehold, type HouseholdDetail } from "@/lib/api/admin";
import { formatPeriod } from "@/lib/dates";
import { describeProblem } from "@/lib/messages";
import { rupees } from "@/lib/plan";

const yes = (value: boolean) => (value ? "Yes" : "No");
const RENEWALS = { manual: "One month at a time", autopay: "AutoPay", off: "AutoPay off" } as const;

function Part({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section aria-label={title} className="border-t border-ink/[0.08] pt-4">
      <h3 className="mb-3 text-sm font-semibold">{title}</h3>
      {children}
    </section>
  );
}

export function StatusBadge({ status }: { status: HouseholdDetail["status"] }) {
  if (status === "active") return <Badge variant="positive">{statusLabels.active}</Badge>;
  if (status === "suspended") return <Badge variant="warning">{statusLabels.suspended}</Badge>;
  return <Badge>{statusLabels.deleted}</Badge>;
}

function Body({ detail }: { detail: HouseholdDetail }) {
  const plan = detail.plan_detail;
  return (
    <div className="space-y-4">
      <Part title="Dates">
        <Facts
          items={[
            ["Joined", day(detail.joined_at)],
            ["Agreed to the terms", day(detail.agreed_at)],
            ["Last WhatsApp message", moment(detail.last_message_at)],
            ["Last record added", moment(detail.last_record_at)],
            ...(detail.suspended_at ? ([["Suspended", moment(detail.suspended_at)]] as [string, ReactNode][]) : []),
            ...(detail.deleted_at ? ([["Deleted", moment(detail.deleted_at)]] as [string, ReactNode][]) : []),
          ]}
        />
      </Part>

      <Part title="Sign-in">
        <Facts
          items={[
            ["WhatsApp", detail.whatsapp ? "Linked" : "Not linked"],
            ["Google", detail.google ? (detail.google_email ?? "Linked") : "Not linked"],
          ]}
        />
      </Part>

      <Part title="Plan">
        <Facts
          items={[
            ["Plan", planLabels[plan.state]],
            ["Trial ends", day(plan.trial_ends_at)],
            ["Paid through", day(plan.paid_through)],
            ["Renewal", plan.renewal ? RENEWALS[plan.renewal] : "—"],
            ["Next charge", day(plan.next_charge_on)],
            ["Grace until", day(plan.grace_until)],
          ]}
        />
        {detail.payments.length > 0 && (
          <ul aria-label="Payments" className="mt-3 divide-y divide-ink/[0.07] text-sm">
            {detail.payments.map((payment) => (
              <li key={payment.id} className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 py-2">
                <span className="tabular-nums">
                  <strong>{rupees(payment.amount_minor)}</strong>
                  <span className="text-ink-soft">
                    {" "}
                    · {day(payment.created_at)}
                    {payment.mode ? ` · ${payment.mode}` : ""}
                  </span>
                </span>
                <Badge variant={payment.status === "paid" ? "positive" : payment.status === "failed" ? "default" : "warning"}>
                  {paymentStatusLabels[payment.status]}
                </Badge>
              </li>
            ))}
          </ul>
        )}
      </Part>

      <Part title="Today's use">
        <div className="space-y-3">
          <Meter label="AI answers" used={detail.usage.ai} limit={detail.usage.ai_limit} />
          <Meter label="Voice notes" used={detail.usage.voice} limit={detail.usage.voice_limit} />
        </div>
      </Part>

      <Part title="Records">
        <CountTable
          caption="Records by state"
          rows={Object.entries(detail.records).map(([key, value]) => ({ key, label: label(recordLabels, key), value }))}
          empty="No records yet."
        />
        <div className="mt-3">
          <Facts
            items={[
              [
                "Dues",
                Object.keys(detail.dues).length
                  ? Object.entries(detail.dues)
                      .map(([key, value]) => `${count(value)} ${label(dueLabels, key).toLowerCase()}`)
                      .join(" · ")
                  : "None",
              ],
              ["Budgets", count(detail.budgets)],
              ["Savings goal set", yes(detail.goal_set)],
            ]}
          />
        </div>
      </Part>

      <Part title="Imports">
        <Facts
          items={[
            [
              "Gmail",
              detail.gmail
                ? `${readable(detail.gmail.status)}${detail.gmail.revoked ? " · revoked" : ""} · last scan ${day(detail.gmail.last_synced_at)}`
                : "Not connected",
            ],
          ]}
        />
        {detail.imports.length > 0 && (
          <ul aria-label="Recent imports" className="mt-3 divide-y divide-ink/[0.07] text-sm">
            {detail.imports.map((run, index) => (
              <li key={`${run.started_at ?? "queued"}-${index}`} className="flex flex-wrap justify-between gap-x-3 gap-y-1 py-2">
                <span>{label(importModeLabels, run.mode)}</span>
                <span className="text-ink-soft">
                  {readable(run.status)}
                  {run.error_code ? ` (${run.error_code})` : ""} · {day(run.started_at)}
                </span>
              </li>
            ))}
          </ul>
        )}
        {detail.statements.length > 0 && (
          <ul aria-label="Statement imports" className="mt-3 divide-y divide-ink/[0.07] text-sm">
            {detail.statements.map((statement) => (
              <li key={`${statement.period_start}-${statement.period_end}`} className="flex flex-wrap justify-between gap-x-3 gap-y-1 py-2">
                <span>Statement · {formatPeriod(statement.period_start, statement.period_end)}</span>
                <span className="text-ink-soft tabular-nums">
                  {count(statement.rows_total)} rows · {statement.reconciled ? "adds up" : "doesn't add up"}
                  {statement.removed ? " · removed" : ""}
                </span>
              </li>
            ))}
          </ul>
        )}
      </Part>

      <Part title="WhatsApp">
        {detail.whatsapp_state ? (
          <Facts
            items={[
              ["Replies", detail.whatsapp_state.replies_on ? "On" : "Off (they sent STOP)"],
              ["Language", detail.whatsapp_state.language ? label(languageLabels, detail.whatsapp_state.language) : "Follows each message"],
              ["Reminders", detail.whatsapp_state.reminders ? "Opted in" : "Not opted in"],
              ["Monthly check-in", detail.whatsapp_state.checkins ? "Opted in" : "Not opted in"],
              ["Pilot consent", day(detail.whatsapp_state.agreed_at)],
            ]}
          />
        ) : (
          <p className="text-sm text-ink-soft">No WhatsApp number linked.</p>
        )}
      </Part>
    </div>
  );
}

/** One household's activity and plan, never its records, messages or contact details. */
export function HouseholdDetailView({
  householdId,
  version,
  onChanged,
  onErased,
  announce,
  focusOnLoad = false,
}: {
  householdId: string;
  /** Bumped by the list to load again (for example after Refresh). */
  version: number;
  onChanged: () => void;
  onErased: () => void;
  announce: (message: string) => void;
  focusOnLoad?: boolean;
}) {
  const detail = useResource(`admin-household:${householdId}:${version}`, (signal) => getHousehold(householdId, signal));
  const heading = useRef<HTMLHeadingElement>(null);
  const loaded = detail.data?.id === householdId;
  useEffect(() => {
    if (focusOnLoad && loaded) heading.current?.focus();
  }, [focusOnLoad, loaded]);

  if (detail.status === "loading") return <LoadingPanel label="Loading the household…" />;
  const data = detail.data;
  return (
    <div className="space-y-4">
      {detail.error !== null && (
        <ProblemNotice
          problem={describeProblem(detail.error, data ? "Couldn't refresh this household" : "This household couldn't be loaded")}
          onRetry={detail.reload}
        />
      )}
      {data && (
        <>
          <div>
            <p className="text-xs font-semibold text-ink-soft">Household</p>
            <h2 ref={heading} tabIndex={-1} className="font-mono text-2xl font-semibold tracking-tight outline-none">
              {data.short_id}
            </h2>
            <p className="mt-0.5 font-mono text-[11px] break-all text-ink-soft">{data.id}</p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              <Badge variant="solid">{kindLabels[data.kind]}</Badge>
              <StatusBadge status={data.status} />
              <Badge>{planLabels[data.plan]}</Badge>
              {data.language && <Badge>{label(languageLabels, data.language)}</Badge>}
            </div>
          </div>
          <RefreshingLabel active={detail.status === "refreshing"}>Updating…</RefreshingLabel>
          <HouseholdActions
            detail={data}
            onUpdated={(next) => {
              detail.replace(next);
              onChanged();
            }}
            onErased={onErased}
            announce={announce}
          />
          <Body detail={data} />
        </>
      )}
    </div>
  );
}
