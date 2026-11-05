"use client";

import { useState } from "react";
import { CountTable, count, Facts, Meter, moment, Panel, RefreshButton } from "@/components/admin/admin-bits";
import { PageHeader } from "@/components/app-shell/page-header";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { LoadingPanel, RefreshingLabel } from "@/components/feedback/states";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { useAction } from "@/hooks/use-action";
import { useResource } from "@/hooks/use-resource";
import { label, languageLabels } from "@/lib/admin-labels";
import { getSignups, tidySignups } from "@/lib/api/admin";
import { describeProblem } from "@/lib/messages";

/** Places against SIGNUP_LIMIT, the WhatsApp waitlist, and tidying sign-ups that never agreed. */
export function SignupsScreen() {
  const signups = useResource("admin-signups", (signal) => getSignups(signal));
  const tidy = useAction();
  const [confirming, setConfirming] = useState(false);
  const [announcement, setAnnouncement] = useState("");
  const data = signups.data;

  async function run() {
    if (!data) return;
    const before = data.stale_pending;
    const next = await tidy.run("tidy", "Sign-ups weren't tidied", () => tidySignups());
    if (!next) return;
    signups.replace(next);
    setConfirming(false);
    const removed = Math.max(0, before - next.stale_pending);
    setAnnouncement(`Tidied: ${count(removed)} ${removed === 1 ? "sign-up" : "sign-ups"} removed.`);
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Sign-ups"
        description="Self-serve places against the limit, and the WhatsApp waitlist. No numbers or names."
        actions={<RefreshButton resource={signups} />}
      />
      <div role="status" aria-live="polite" className="text-sm font-medium">
        {announcement}
      </div>
      <RefreshingLabel active={signups.status === "refreshing"}>Updating…</RefreshingLabel>
      {signups.status === "loading" && <LoadingPanel label="Loading sign-ups…" />}
      {signups.error !== null && (
        <ProblemNotice
          problem={describeProblem(signups.error, data ? "Couldn't refresh — showing the last loaded counts" : "Sign-ups couldn't be loaded")}
          onRetry={signups.reload}
        />
      )}
      {data && (
        <div className="grid items-start gap-5 lg:grid-cols-2">
          <div className="space-y-5">
            <Panel
              title="Places"
              description={data.open ? "Sign-up is open." : data.enabled ? "Sign-up is full: new people join the waitlist." : "Sign-up is off."}
            >
              <Meter label="Agreed households" used={data.agreed} limit={data.limit} />
              <div className="mt-4">
                <Facts
                  items={[
                    ["SIGNUP_ENABLED", data.enabled ? "On" : "Off"],
                    ["Open now", data.open ? "Yes" : "No"],
                    ["Started but not agreed", count(data.pending)],
                    ["Not agreed after a week", count(data.stale_pending)],
                  ]}
                />
              </div>
            </Panel>
            <Panel
              title="Tidy"
              description="Forget sign-ups that never agreed within a week, and finished sign-in attempts — as the server's accounts.cli tidy does."
            >
              {tidy.problem && <ProblemNotice className="mb-3" problem={tidy.problem} />}
              <Button variant="outline" disabled={data.stale_pending === 0} onClick={() => setConfirming(true)}>
                {data.stale_pending === 0
                  ? "Nothing to tidy"
                  : `Tidy ${count(data.stale_pending)} ${data.stale_pending === 1 ? "sign-up" : "sign-ups"}`}
              </Button>
            </Panel>
          </div>
          <Panel title="Waitlist" description="People who sent JOIN while FinBoy was full.">
            <p className="text-[1.75rem] leading-none font-semibold tracking-[-0.025em]">{count(data.waitlist)}</p>
            <p className="mt-2 text-xs text-ink-soft">
              {data.oldest_waiting_since ? `Waiting since ${moment(data.oldest_waiting_since)}` : "Nobody is waiting."}
            </p>
            <div className="mt-4">
              <CountTable
                caption="Waitlist by language"
                rows={Object.entries(data.waitlist_languages).map(([key, value]) => ({ key, label: label(languageLabels, key), value }))}
                empty="No languages to show."
              />
            </div>
          </Panel>
        </div>
      )}
      <AlertDialog open={confirming} onOpenChange={(open) => !tidy.busy && setConfirming(open)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Tidy sign-ups?</AlertDialogTitle>
            <AlertDialogDescription>
              Sign-ups that never agreed within a week are forgotten completely, as if the person had answered No. Agreed
              households aren&apos;t touched.
            </AlertDialogDescription>
          </AlertDialogHeader>
          {tidy.problem && <ProblemNotice problem={tidy.problem} />}
          <AlertDialogFooter>
            <AlertDialogCancel disabled={tidy.busy !== null}>Cancel</AlertDialogCancel>
            <Button disabled={tidy.busy !== null} onClick={() => void run()}>
              {tidy.busy ? "Tidying…" : "Tidy now"}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
