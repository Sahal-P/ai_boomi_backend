"use client";

import { ArrowRight, Eye, History, Mail, Pause, Play, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useHouseholdAccess } from "@/components/app-shell/household-context";
import { PageHeader } from "@/components/app-shell/page-header";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { LoadingPanel } from "@/components/feedback/states";
import { CoverageSummary } from "@/components/sources/coverage-summary";
import { ImportHistory } from "@/components/sources/import-history";
import { UploadStager } from "@/components/sources/upload-stager";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAction } from "@/hooks/use-action";
import { useResource } from "@/hooks/use-resource";
import { authorizeUrl, getConnections, oauthErrorMessage, scanNow, setScansAllowed, type MailConnection } from "@/lib/api/mail";
import { getSummary } from "@/lib/api/money";
import { formatDayTime } from "@/lib/dates";
import { describeProblem } from "@/lib/messages";
import { cn } from "@/lib/utils";

const connectionState: Record<
  MailConnection["status"],
  { label: string; variant: "positive" | "warning" | "outline" | "destructive" }
> = {
  active: { label: "Scans allowed", variant: "positive" },
  paused: { label: "Scans paused", variant: "warning" },
  error: { label: "Needs reconnecting", variant: "destructive" },
  revoked: { label: "Disconnected", variant: "outline" },
};

export function SourcesScreen({ errorCode, intent }: { errorCode: string | null; intent: string | null }) {
  const router = useRouter();
  const { signIn } = useHouseholdAccess();
  const connections = useResource("connections", (signal) => getConnections(signal));
  const summary = useResource("summary:current", (signal) => getSummary(null, signal));
  const action = useAction();
  const [notice, setNotice] = useState<string | null>(null);
  const connectRef = useRef<HTMLAnchorElement>(null);
  const oauthMessage = oauthErrorMessage(errorCode);
  const live = (connections.data ?? []).filter((item) => item.status !== "revoked");
  const wantsGmail = intent === "gmail";

  useEffect(() => {
    if (wantsGmail && connections.status === "ready" && !live.length) connectRef.current?.focus();
  }, [wantsGmail, connections.status, live.length]);

  async function scan(connection: MailConnection) {
    setNotice(null);
    const started = await action.run(`scan:${connection.id}`, "The scan didn't start", () => scanNow(connection.id));
    if (started) router.push(`/import/${started.import_run_id}`);
  }

  async function allow(connection: MailConnection, allowed: boolean) {
    setNotice(null);
    const done = await action.run(
      `${allowed ? "allow" : "pause"}:${connection.id}`,
      allowed ? "Scans weren't allowed" : "Scans weren't paused",
      () => setScansAllowed(connection.id, allowed),
    );
    if (done) {
      setNotice(
        allowed
          ? "Scans are allowed again. Nothing was scanned yet — use Scan now when you're ready."
          : "Scans are paused. A scan that was running stops at its next safe point; new scans won't start until you allow them.",
      );
      connections.reload();
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Sources"
        description="Where FinBoy reads your money emails. Scans are manual: nothing runs until you start one."
      />
      {oauthMessage && (
        <ProblemNotice
          problem={{ title: "Gmail wasn't connected", detail: oauthMessage, reference: null, kind: "unknown", code: errorCode }}
        />
      )}
      <div role="status" aria-live="polite">
        {notice && (
          <p className="rounded-2xl border border-ink/15 bg-white/60 p-4 text-sm text-ink">{notice}</p>
        )}
      </div>

      <div className="grid items-start gap-5 xl:grid-cols-[1.25fr_1fr]">
        <div className="space-y-5">
          <section aria-labelledby="accounts-title" className="surface rounded-3xl p-5 sm:p-6">
            <h2 id="accounts-title" className="text-lg font-semibold">
              Gmail
            </h2>
            {connections.status === "loading" && <LoadingPanel className="mt-4 shadow-none" label="Loading your connected account…" />}
            {connections.error !== null && (
              <ProblemNotice
                className="mt-4"
                problem={describeProblem(connections.error, "Your Gmail connection couldn't be loaded")}
                onRetry={connections.reload}
              />
            )}
            {connections.data && !live.length && signIn?.gmail === false && (
              <p className="mt-3 text-sm leading-relaxed text-ink-soft">
                Gmail import is invite-only while Google reviews FinBoy. Until then, add money in a
                tap from{" "}
                <Link href="/dashboard" className="font-semibold text-ink underline underline-offset-4">
                  Overview
                </Link>{" "}
                or by voice on WhatsApp.
              </p>
            )}
            {connections.data && !live.length && signIn?.gmail !== false && (
              <div className="mt-3">
                <p className="text-sm leading-relaxed text-ink-soft">
                  Connect read-only Gmail access to scan the last 30 days for bank alerts, receipts
                  and bills. FinBoy can&apos;t send, edit or delete your emails.
                </p>
                <Button asChild className={cn("mt-4", wantsGmail && "ring-3 ring-ring/50")}>
                  <a ref={connectRef} href={authorizeUrl()}>
                    Connect Gmail <ArrowRight aria-hidden="true" />
                  </a>
                </Button>
              </div>
            )}
            {live.length > 0 && (
              <ul className="mt-4 space-y-4">
                {live.map((connection) => {
                  const state = connectionState[connection.status];
                  return (
                    <li key={connection.id} className="rounded-2xl border p-4">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="flex min-w-0 items-start gap-3">
                          <Mail className="mt-0.5 size-5 shrink-0 text-ink" aria-hidden="true" />
                          <div className="min-w-0">
                            <p className="font-semibold break-all">{connection.account_email_masked}</p>
                            <p className="mt-0.5 text-sm text-ink-soft">
                              Last successful scan:{" "}
                              {connection.last_synced_at ? formatDayTime(connection.last_synced_at) : "not yet"}
                            </p>
                          </div>
                        </div>
                        <Badge variant={state.variant}>{state.label}</Badge>
                      </div>
                      {connection.status === "error" && (
                        <p className="mt-3 text-sm text-amber-900">
                          Google access expired or was revoked. Reconnect to scan again — your
                          existing records stay.
                        </p>
                      )}
                      <div className="mt-4 flex flex-wrap gap-2">
                        {connection.status === "active" && (
                          <>
                            <Button disabled={action.busy !== null} onClick={() => void scan(connection)}>
                              <RefreshCw aria-hidden="true" />
                              {action.busy === `scan:${connection.id}` ? "Starting scan…" : "Scan now"}
                            </Button>
                            <Button
                              variant="outline"
                              disabled={action.busy !== null}
                              onClick={() => void allow(connection, false)}
                            >
                              <Pause aria-hidden="true" /> Pause scans
                            </Button>
                          </>
                        )}
                        {connection.status === "paused" && (
                          <Button disabled={action.busy !== null} onClick={() => void allow(connection, true)}>
                            <Play aria-hidden="true" /> Allow scans
                          </Button>
                        )}
                        {connection.status === "error" && (
                          <Button asChild>
                            <a href={authorizeUrl()}>
                              Reconnect Gmail <ArrowRight aria-hidden="true" />
                            </a>
                          </Button>
                        )}
                      </div>
                      {connection.status === "paused" && (
                        <p className="mt-2 text-xs text-ink-soft">
                          Allowing scans doesn&apos;t start one or resume an earlier import.
                        </p>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
            {action.problem && <ProblemNotice className="mt-4" problem={action.problem} />}
            {connections.data && (
              <p className="mt-4 text-xs leading-relaxed text-ink-soft">
                To revoke access or delete imported records, go to{" "}
                <Link href="/privacy" className="font-semibold text-ink underline underline-offset-4">
                  Privacy &amp; data
                </Link>
                .
              </p>
            )}
          </section>

          <UploadStager />
        </div>

        <div className="space-y-5">
          <section aria-labelledby="coverage-title" className="surface rounded-3xl p-5 sm:p-6">
            <h2 id="coverage-title" className="text-lg font-semibold">
              What&apos;s covered
            </h2>
            {summary.status === "loading" && <LoadingPanel className="mt-4 shadow-none" label="Checking coverage…" />}
            {summary.error !== null && (
              <ProblemNotice
                className="mt-4"
                problem={describeProblem(summary.error, "Coverage couldn't be loaded")}
                onRetry={summary.reload}
              />
            )}
            {summary.data && <CoverageSummary className="mt-4" coverage={summary.data.coverage} />}
          </section>

          <section aria-labelledby="history-title" className="surface rounded-3xl p-5 sm:p-6">
            <h2 id="history-title" className="flex items-center gap-2 text-lg font-semibold">
              <History className="size-5 text-ink" aria-hidden="true" /> Recent imports
            </h2>
            <ImportHistory />
          </section>

          <section aria-labelledby="sample-title" className="surface rounded-3xl p-5 sm:p-6">
            <h2 id="sample-title" className="flex items-center gap-2 text-lg font-semibold">
              <Eye className="size-5 text-ink" aria-hidden="true" /> Explore sample data
            </h2>
            <p className="mt-1 text-sm leading-relaxed text-ink-soft">
              A read-only synthetic household. Viewing it never adds anything to your records.
            </p>
            <Button asChild variant="outline" className="mt-4">
              <Link href="/demo">Open the sample</Link>
            </Button>
          </section>
        </div>
      </div>
    </div>
  );
}
