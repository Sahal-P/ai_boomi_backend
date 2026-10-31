"use client";

import { Mail, ShieldCheck, Trash2, Unplug } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { useHouseholdAccess } from "@/components/app-shell/household-context";
import { PageHeader } from "@/components/app-shell/page-header";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { LoadingPanel } from "@/components/feedback/states";
import { AccountSection } from "@/components/privacy/account-section";
import { DeletionDialog } from "@/components/privacy/deletion-dialog";
import { ExportButton } from "@/components/privacy/export-button";
import { Button } from "@/components/ui/button";
import { useResource } from "@/hooks/use-resource";
import { getConnections, type MailConnection } from "@/lib/api/mail";
import { getAuditEvents, getIsolation, type AuditEvent } from "@/lib/api/privacy";
import { formatDayTime } from "@/lib/dates";
import { auditEventLabels } from "@/lib/labels";
import { describeProblem } from "@/lib/messages";

function eventLink(event: AuditEvent): string | null {
  if (event.subject_type === "import_run") return `/import/${event.subject_id}`;
  if (event.subject_type === "transaction") return `/transactions?selected=${event.subject_id}`;
  return null;
}

type Target = { kind: "delete" } | { kind: "disconnect"; connection: MailConnection } | null;

export function PrivacyScreen() {
  const connections = useResource("connections", (signal) => getConnections(signal));
  const isolation = useResource("isolation", (signal) => getIsolation(signal));
  const events = useResource("audit", (signal) => getAuditEvents(signal));
  const { signIn } = useHouseholdAccess();
  const [target, setTarget] = useState<Target>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const live = (connections.data ?? []).filter((item) => item.status !== "revoked");
  const exportVersion = isolation.data?.data_version ?? null;
  const separated = isolation.data && (isolation.data.demo_only_transactions > 0 || isolation.data.mixed_transactions > 0 || isolation.data.quarantined_obligations > 0);

  return (
    <div className="space-y-5">
      <PageHeader
        title="Privacy & data"
        description="What FinBoy keeps, and how to export, disconnect or delete it. Each choice shows its effect first."
      />
      <div role="status" aria-live="polite">
        {notice && <p className="rounded-2xl bg-white/60 p-4 text-sm font-medium">{notice}</p>}
      </div>

      <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-[1.4fr_1fr]">
        <div className="space-y-5">
          <AccountSection />
          <section aria-labelledby="access-title" className="surface rounded-3xl p-5 sm:p-6">
            <h2 id="access-title" className="text-lg font-semibold">Gmail access</h2>
            {connections.status === "loading" && <LoadingPanel className="mt-3 shadow-none" label="Loading connected accounts…" />}
            {connections.error !== null && (
              <ProblemNotice className="mt-3" problem={describeProblem(connections.error, "Connected accounts couldn't be loaded")} onRetry={connections.reload} />
            )}
            {connections.data && !live.length && (
              <p className="mt-2 text-sm text-ink-soft">
                No Gmail account is connected.{" "}
                {signIn?.gmail === false ? (
                  "Gmail import is invite-only while Google reviews FinBoy."
                ) : (
                  <>
                    <Link href="/sources" className="font-semibold text-ink underline underline-offset-4">Go to Sources</Link> to add one.
                  </>
                )}
              </p>
            )}
            {live.length > 0 && (
              <ul className="mt-3 space-y-3">
                {live.map((connection) => (
                  <li key={connection.id} className="flex flex-wrap items-center justify-between gap-3 rounded-2xl bg-well p-4 ring-1 ring-ink/5">
                    <span className="flex min-w-0 items-center gap-3">
                      <Mail className="size-5 shrink-0 text-ink" aria-hidden="true" />
                      <span className="min-w-0">
                        <span className="block font-semibold break-all">{connection.account_email_masked}</span>
                        <span className="block text-xs text-ink-soft">Read-only · can&apos;t send, edit or delete your emails</span>
                      </span>
                    </span>
                    <Button variant="outline" onClick={() => { setNotice(null); setTarget({ kind: "disconnect", connection }); }}>
                      <Unplug aria-hidden="true" /> Disconnect
                    </Button>
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-3 text-xs leading-relaxed text-ink-soft">
              Pause or allow scans from <Link href="/sources" className="font-semibold underline underline-offset-4">Sources</Link>. Disconnecting revokes Google access; it doesn&apos;t delete records unless you choose that.
            </p>
          </section>

          <section aria-labelledby="export-title" className="surface rounded-3xl p-5 sm:p-6">
            <h2 id="export-title" className="text-lg font-semibold">Export your records</h2>
            <p className="mt-1 text-sm leading-relaxed text-ink-soft">
              A structured JSON copy of your transactions, obligations and corrections. It never
              includes email bodies, evidence snippets, account numbers or credentials, and it&apos;s
              only created when you press the button.
            </p>
            {isolation.error !== null && (
              <ProblemNotice className="mt-3" problem={describeProblem(isolation.error, "Export isn't available right now")} onRetry={isolation.reload} />
            )}
            <div className="mt-4">
              <ExportButton version={exportVersion} onConflict={isolation.reload} variant="default" />
            </div>
          </section>

          <section aria-labelledby="delete-title" className="surface rounded-3xl p-5 sm:p-6">
            <h2 id="delete-title" className="text-lg font-semibold">Delete imported records</h2>
            <p className="mt-1 text-sm leading-relaxed text-ink-soft">
              Removes email-derived records, evidence and obligations. You&apos;ll see exactly what
              would be deleted and what stays before anything happens.
            </p>
            <Button variant="destructive" className="mt-4" onClick={() => { setNotice(null); setTarget({ kind: "delete" }); }}>
              <Trash2 aria-hidden="true" /> Preview deletion
            </Button>
          </section>

          {separated && isolation.data && (
            <section aria-labelledby="separation-title" className="surface rounded-3xl p-5 sm:p-6">
              <h2 id="separation-title" className="text-lg font-semibold">Sample data kept separate</h2>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-relaxed text-ink-soft">
                {isolation.data.demo_only_transactions > 0 && (
                  <li>{isolation.data.demo_only_transactions} records from an earlier sample import are separated and never count in your household totals.</li>
                )}
                {isolation.data.mixed_transactions > 0 && (
                  <li>
                    {isolation.data.mixed_transactions} records mixed sample and household emails, so they&apos;re{" "}
                    <Link href="/transactions?dataset=quarantined&scope=all" className="font-semibold text-ink underline underline-offset-4">on hold</Link>{" "}
                    and excluded until repaired.
                  </li>
                )}
                {isolation.data.quarantined_obligations > 0 && (
                  <li>{isolation.data.quarantined_obligations} obligations are on hold for the same reason.</li>
                )}
              </ul>
            </section>
          )}

          <section aria-labelledby="activity-title" className="surface rounded-3xl p-5 sm:p-6">
            <h2 id="activity-title" className="text-lg font-semibold">Activity</h2>
            {events.status === "loading" && <LoadingPanel className="mt-3 shadow-none" label="Loading activity…" />}
            {events.error !== null && (
              <ProblemNotice className="mt-3" problem={describeProblem(events.error, "Activity history couldn't be loaded")} onRetry={events.reload} />
            )}
            {events.data && !events.data.length && <p className="mt-2 text-sm text-ink-soft">No activity yet.</p>}
            {events.data && events.data.length > 0 && (
              <ol className="mt-3 max-h-96 space-y-3 overflow-y-auto pr-1">
                {events.data.map((event) => {
                  const href = eventLink(event);
                  const label = auditEventLabels[event.event_type] ?? "Account activity";
                  return (
                    <li key={event.id} className="border-l-2 border-ink/10 pl-4">
                      {href ? (
                        <Link href={href} className="text-sm font-medium text-ink underline underline-offset-4">{label}</Link>
                      ) : (
                        <p className="text-sm font-medium">{label}</p>
                      )}
                      <p className="text-xs text-ink-soft">{formatDayTime(event.created_at)}</p>
                    </li>
                  );
                })}
              </ol>
            )}
          </section>
        </div>

        <aside className="rounded-3xl bg-secondary/70 p-5 text-sm leading-relaxed sm:p-6">
          <ShieldCheck className="size-7 text-ink" aria-hidden="true" />
          <h2 className="mt-3 text-lg font-semibold">What FinBoy keeps</h2>
          <p className="mt-2 text-ink-soft">
            Masked account details, message identifiers and hashes, structured financial records,
            and evidence snippets of up to 80 characters per field. Gmail refresh tokens are encrypted.
          </p>
          <h3 className="mt-5 font-semibold">What it doesn&apos;t keep</h3>
          <p className="mt-1 text-ink-soft">
            Raw email bodies, uploaded .eml files, WhatsApp screenshots, full email addresses, OAuth
            codes, access tokens, your questions and voice recordings.
          </p>
          <h3 className="mt-5 font-semibold">Backups</h3>
          <p className="mt-1 text-ink-soft">
            On the hosted app, private server backups may keep structured records for up to seven
            days after you delete them.
          </p>
          <h3 className="mt-5 font-semibold">Not training data</h3>
          <p className="mt-1 text-ink-soft">
            Financial emails are never used to train models. Relevant content may be processed by the
            backend&apos;s extraction provider to create structured records. Voice is transcribed by
            the configured speech provider (Sarvam AI, Groq or OpenAI) and never stored. Questions
            are sent to OpenAI to understand and word the reply; household
            record amounts are calculated by FinBoy and are not sent for answer wording.
            Liquid AI quickly tells what a message, question or photo is about, so common ones are
            answered sooner; it gets no record amounts.
            Where WhatsApp is enabled, payment screenshots are read by OpenAI and never stored.
          </p>
        </aside>
      </div>

      <DeletionDialog
        target={target}
        exportVersion={exportVersion}
        onClose={() => setTarget(null)}
        onDone={(message) => {
          setTarget(null);
          setNotice(message);
          connections.reload();
          isolation.reload();
          events.reload();
        }}
      />
    </div>
  );
}
