"use client";

import type { ReactNode } from "react";
import { Facts, Panel, RefreshButton, count } from "@/components/admin/admin-bits";
import { PageHeader } from "@/components/app-shell/page-header";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { LoadingPanel, RefreshingLabel } from "@/components/feedback/states";
import { Badge } from "@/components/ui/badge";
import { useResource } from "@/hooks/use-resource";
import { envName, flagLabels, label, limitLabels, providerLabels, providerStateLabels } from "@/lib/admin-labels";
import { getSystem, type SystemStatus } from "@/lib/api/admin";
import { describeProblem } from "@/lib/messages";

const SCHEMA: Record<SystemStatus["schema_status"], string> = {
  current: "Current",
  behind: "Behind — run the migration",
  unavailable: "Unavailable",
};

function Setting({ name, envKey, children }: { name: string; envKey: string; children: ReactNode }) {
  return (
    <li className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 py-2.5">
      <span className="min-w-0">
        <span className="block text-sm font-medium">{name}</span>
        <span className="block font-mono text-[11px] break-all text-ink-soft">{envKey}</span>
      </span>
      {children}
    </li>
  );
}

function Body({ data }: { data: SystemStatus }) {
  return (
    // Two stacks rather than grid rows, so a short card never leaves a gap beside a tall one.
    <div className="grid items-start gap-5 lg:grid-cols-2">
      <div className="space-y-5">
        <Panel title="Service">
          <Facts
            items={[
              ["Environment", data.environment],
              ["Release", data.release ? <span className="font-mono">{data.release.slice(0, 12)}</span> : "Not a release folder"],
              ["Database", data.database === "connected" ? "Connected" : "Unavailable"],
              ["Schema", `${SCHEMA[data.schema_status]} · ${data.schema_head}`],
              ["Imports running", data.active_imports === null ? "—" : count(data.active_imports)],
              ["Payments still open", data.open_payments === null ? "—" : count(data.open_payments)],
              ["PayU", data.payu_environment === "production" ? "Live" : "Test"],
            ]}
          />
        </Panel>
        <Panel title="Switches">
          <ul className="divide-y divide-ink/[0.07]">
            {Object.entries(data.flags).map(([key, on]) => (
              <Setting key={key} name={label(flagLabels, key)} envKey={envName(key)}>
                <Badge variant={on ? "solid" : "default"}>{on ? "On" : "Off"}</Badge>
              </Setting>
            ))}
          </ul>
        </Panel>
      </div>
      <div className="space-y-5">
        <Panel title="Providers" description="Whether each is configured. Keys are never shown.">
          <ul className="divide-y divide-ink/[0.07]">
            {Object.entries(data.providers).map(([key, state]) => (
              <li key={key} className="flex items-center justify-between gap-3 py-2.5 text-sm">
                <span className="font-medium">{label(providerLabels, key)}</span>
                <Badge variant={state === "configured" ? "positive" : state === "missing" ? "warning" : "default"}>
                  {providerStateLabels[state]}
                </Badge>
              </li>
            ))}
          </ul>
        </Panel>
        <Panel title="Limits">
          <ul className="divide-y divide-ink/[0.07]">
            {Object.entries(data.limits).map(([key, value]) => {
              const known = limitLabels[key];
              return (
                <Setting key={key} name={known?.label ?? label({}, key)} envKey={envName(key)}>
                  <span className="text-sm tabular-nums">
                    <strong>{count(value)}</strong>
                    {known ? <span className="text-ink-soft"> {known.unit}</span> : null}
                  </span>
                </Setting>
              );
            })}
          </ul>
        </Panel>
      </div>
    </div>
  );
}

/** Read-only: every setting is changed in /etc/finboy/production.env, then a restart. */
export function SystemScreen() {
  const system = useResource("admin-system", (signal) => getSystem(signal));
  return (
    <div className="space-y-5">
      <PageHeader
        title="System"
        description={
          <>
            Read-only. To change a setting, edit <span className="font-mono">/etc/finboy/production.env</span> on the server
            and restart <span className="font-mono">finboy.service</span>; its safety checks run at start-up.
          </>
        }
        actions={<RefreshButton resource={system} />}
      />
      <RefreshingLabel active={system.status === "refreshing"}>Updating…</RefreshingLabel>
      {system.status === "loading" && <LoadingPanel label="Loading system status…" />}
      {system.error !== null && (
        <ProblemNotice
          problem={describeProblem(system.error, system.data ? "Couldn't refresh — showing the last loaded status" : "System status couldn't be loaded")}
          onRetry={system.reload}
        />
      )}
      {system.data && <Body data={system.data} />}
    </div>
  );
}
