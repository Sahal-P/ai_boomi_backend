"use client";

import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { CountTable, count, Meter, Panel, RefreshButton, StatTile } from "@/components/admin/admin-bits";
import { PageHeader } from "@/components/app-shell/page-header";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { LoadingPanel, RefreshingLabel } from "@/components/feedback/states";
import { Button } from "@/components/ui/button";
import { useResource } from "@/hooks/use-resource";
import { kindLabels, label, planLabels, statusLabels, usageLabels } from "@/lib/admin-labels";
import { getOverview, KINDS, PLAN_STATES, type Overview } from "@/lib/api/admin";
import { describeProblem } from "@/lib/messages";
import { rupees } from "@/lib/plan";

const rowsOf = (values: Record<string, number>, labels: Record<string, string>) =>
  Object.entries(values).map(([key, value]) => ({ key, label: label(labels, key), value }));

function OverviewBody({ data }: { data: Overview }) {
  const { households, signups, active, plans } = data;
  const n = (values: Record<string, number>, key: string) => values[key] ?? 0;
  return (
    <>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile
          label="Self-serve households"
          value={count(n(households, "self_serve"))}
          detail={`${count(signups.pending)} pending · ${count(signups.waitlist)} on the waitlist`}
        />
        <StatTile
          label="Active in the last 7 days"
          value={count(n(active, "week"))}
          detail={`${count(n(active, "today"))} today · ${count(n(active, "month"))} in 30 days`}
        />
        <StatTile
          label="On paid Premium"
          value={count(n(plans, "active"))}
          detail={`${count(n(plans, "trial"))} in trial · ${count(n(plans, "grace"))} in grace · ${count(n(plans, "free"))} free`}
        />
        <StatTile
          label="Received this month"
          value={data.billing_enabled ? rupees(data.received_this_month_minor) : "Billing off"}
          detail={
            data.billing_enabled
              ? `${count(data.paid_this_month)} payments · ${count(data.open_payments)} still open`
              : "Nothing is charged while BILLING_ENABLED is false."
          }
        />
      </div>

      {/* Two stacks rather than grid rows, so a short card never leaves a gap beside a tall one. */}
      <div className="grid items-start gap-5 lg:grid-cols-2">
        <div className="space-y-5">
          <Panel
            title="Sign-ups"
            description={
              signups.open
                ? "Sign-up is open."
                : signups.enabled
                  ? "Sign-up is full: new people join the waitlist."
                  : "Sign-up is off (SIGNUP_ENABLED)."
            }
            actions={
              <Button asChild variant="ghost" size="sm">
                <Link href="/admin/signups">
                  Sign-ups <ChevronRight aria-hidden="true" />
                </Link>
              </Button>
            }
          >
            <Meter label="Places taken" used={signups.agreed} limit={signups.limit} />
            <p className="mt-3 text-xs text-ink-soft">
              {count(signups.pending)} haven&apos;t agreed yet · {count(signups.waitlist)} waiting on WhatsApp
            </p>
          </Panel>
          <Panel title="Plans" description="Active households only.">
            <CountTable
              caption="Households by plan"
              rows={PLAN_STATES.map((state) => ({ key: state, label: planLabels[state], value: n(plans, state) }))}
              empty="No plans to show."
            />
          </Panel>
          <Panel title="Today's use" description="Across every household, since midnight in India.">
            <CountTable caption="Use today" rows={rowsOf(data.usage_today, usageLabels)} empty="Nothing used yet today." />
          </Panel>
        </div>
        <div className="space-y-5">
          <Panel title="Households" description="Active households by kind, then paused and deleted ones.">
            <CountTable
              caption="Households by kind"
              rows={[
                ...KINDS.map((kind) => ({ key: kind, label: kindLabels[kind], value: n(households, kind) })),
                { key: "suspended", label: statusLabels.suspended, value: n(households, "suspended") },
                { key: "deleted", label: statusLabels.deleted, value: n(households, "deleted") },
              ]}
              empty="No households yet."
            />
          </Panel>
          <Panel title="WhatsApp messages sent" description="The last 7 days, by Meta's latest delivery state.">
            <CountTable
              caption="WhatsApp deliveries in the last 7 days"
              rows={rowsOf(data.deliveries_week, {})}
              empty="No messages sent in 7 days."
            />
          </Panel>
          <Panel title="Imports" description="Gmail, email and statement imports in the last 7 days.">
            <CountTable caption="Imports in the last 7 days" rows={rowsOf(data.imports_week, {})} empty="No imports in 7 days." />
          </Panel>
        </div>
      </div>
    </>
  );
}

export function OverviewScreen() {
  const overview = useResource("admin-overview", (signal) => getOverview(signal));
  return (
    <div className="space-y-5">
      <PageHeader
        title="Overview"
        description="How FinBoy is used right now: counts and dates, never a household's records."
        actions={<RefreshButton resource={overview} />}
      />
      <RefreshingLabel active={overview.status === "refreshing"}>Updating the counts…</RefreshingLabel>
      {overview.status === "loading" && <LoadingPanel label="Loading the overview…" />}
      {overview.error !== null && (
        <ProblemNotice
          problem={describeProblem(
            overview.error,
            overview.data ? "Couldn't refresh — showing the last loaded counts" : "The overview couldn't be loaded",
          )}
          onRetry={overview.reload}
        />
      )}
      {overview.data && <OverviewBody data={overview.data} />}
    </div>
  );
}
