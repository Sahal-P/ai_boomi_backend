"use client";

import { Check, Copy } from "lucide-react";
import Link from "next/link";
import { useId, useState } from "react";
import { day, moment, Panel, RefreshButton } from "@/components/admin/admin-bits";
import { PageHeader } from "@/components/app-shell/page-header";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { LoadingPanel } from "@/components/feedback/states";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAction } from "@/hooks/use-action";
import { useResource } from "@/hooks/use-resource";
import {
  addAdmin,
  disableAdmin,
  listAdmins,
  listAdminSessions,
  signOutOtherSessions,
  type AdminRow,
  type CreatedAdmin,
} from "@/lib/api/admin";
import { describeProblem } from "@/lib/messages";

type Confirm = { kind: "disable"; admin: AdminRow } | { kind: "sessions" } | null;

function AddAdmin({ onAdded }: { onAdded: () => void }) {
  const ids = useId();
  const [email, setEmail] = useState("");
  const [created, setCreated] = useState<CreatedAdmin | null>(null);
  const [copied, setCopied] = useState(false);
  const add = useAction();

  async function submit() {
    const result = await add.run("add", "The admin wasn't added", () => addAdmin(email.trim()));
    if (!result) return;
    setCreated(result);
    setCopied(false);
    setEmail("");
    onAdded();
  }

  async function copy() {
    if (!created) return;
    try {
      await navigator.clipboard.writeText(created.temporary_password);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  return (
    <Panel
      title="Add an admin"
      description="They get a temporary password, shown once here, and must choose their own when they first sign in."
    >
      <form
        className="flex flex-wrap items-end gap-2"
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <div className="min-w-0 flex-1 basis-56">
          <label htmlFor={`${ids}-email`} className="text-sm font-semibold">
            Their email
          </label>
          <Input
            id={`${ids}-email`}
            type="email"
            autoComplete="off"
            spellCheck={false}
            required
            maxLength={254}
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="mt-1.5"
          />
        </div>
        <Button type="submit" disabled={add.busy !== null || !email.trim()}>
          {add.busy ? "Adding…" : "Add admin"}
        </Button>
      </form>
      {add.problem && <ProblemNotice className="mt-3" problem={add.problem} />}
      <div role="status" aria-live="polite">
        {created && (
          <div className="mt-4 rounded-2xl bg-white/70 p-4 shadow-hairline">
            <p className="text-sm font-semibold">
              {created.email} can sign in with this temporary password:
            </p>
            <div className="mt-2 flex flex-wrap gap-2">
              <code className="min-w-0 flex-1 rounded-lg bg-ink/[0.06] px-3 py-2.5 font-mono text-sm break-all select-all">
                {created.temporary_password}
              </code>
              <Button type="button" variant="outline" onClick={() => void copy()}>
                {copied ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
                {copied ? "Copied" : "Copy"}
              </Button>
            </div>
            <p className="mt-2 text-xs text-ink-soft">
              It isn&apos;t shown again. Send it to them privately, not in the same message as the email address.
            </p>
            <Button type="button" variant="ghost" size="sm" className="mt-2" onClick={() => setCreated(null)}>
              Hide it
            </Button>
          </div>
        )}
      </div>
    </Panel>
  );
}

/** Admin accounts, adding and disabling them, and this admin's own signed-in browsers. */
export function AdminsScreen() {
  const admins = useResource("admin-accounts", (signal) => listAdmins(signal));
  const sessions = useResource("admin-sessions", (signal) => listAdminSessions(signal));
  const act = useAction();
  const [confirm, setConfirm] = useState<Confirm>(null);
  const [announcement, setAnnouncement] = useState("");

  async function run() {
    if (!confirm) return;
    if (confirm.kind === "disable") {
      const rows = await act.run("disable", "The admin wasn't disabled", () => disableAdmin(confirm.admin.id));
      if (!rows) return;
      admins.replace(rows);
      setAnnouncement(`${confirm.admin.email} is disabled and signed out.`);
    } else {
      const rows = await act.run("sessions", "Your other browsers weren't signed out", () => signOutOtherSessions());
      if (!rows) return;
      sessions.replace(rows);
      setAnnouncement("Your other browsers are signed out.");
    }
    setConfirm(null);
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Admins"
        description="Who can open this panel. Accounts can also be managed on the server with the admin CLI."
        actions={
          <>
            <Button asChild variant="outline">
              <Link href="/admin/password">Change your password</Link>
            </Button>
            <RefreshButton resource={{ ...admins, reload: () => (admins.reload(), sessions.reload()) }} />
          </>
        }
      />
      <div role="status" aria-live="polite" className="text-sm font-medium">
        {announcement}
      </div>
      <div className="grid items-start gap-5 lg:grid-cols-2">
        <Panel title="Admin accounts">
          {admins.status === "loading" && <LoadingPanel label="Loading admins…" />}
          {admins.error !== null && (
            <ProblemNotice problem={describeProblem(admins.error, "Admins couldn't be loaded")} onRetry={admins.reload} />
          )}
          {admins.data && (
            <ul aria-label="Admin accounts" className="divide-y divide-ink/[0.07]">
              {admins.data.map((admin) => (
                <li key={admin.id} className="flex flex-wrap items-start justify-between gap-x-3 gap-y-2 py-3">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold break-all">{admin.email}</p>
                    <p className="mt-0.5 text-xs text-ink-soft">
                      Added {day(admin.created_at)} · last sign-in {admin.last_login_at ? moment(admin.last_login_at) : "never"}
                    </p>
                    <div className="mt-1.5 flex flex-wrap gap-1.5">
                      {admin.you && <Badge variant="solid">You</Badge>}
                      {admin.active ? <Badge variant="positive">Active</Badge> : <Badge>Disabled</Badge>}
                      {admin.active && admin.must_change_password && <Badge variant="warning">Temporary password</Badge>}
                    </div>
                  </div>
                  {admin.active && !admin.you && (
                    <Button size="sm" variant="outline" onClick={() => (act.clear(), setConfirm({ kind: "disable", admin }))}>
                      Disable
                    </Button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Panel>
        <AddAdmin onAdded={admins.reload} />
        <Panel
          title="Your signed-in browsers"
          description="Each lasts a few hours. Changing your password signs out the others."
          actions={
            sessions.data && sessions.data.length > 1 ? (
              <Button size="sm" variant="outline" onClick={() => (act.clear(), setConfirm({ kind: "sessions" }))}>
                Sign out the others
              </Button>
            ) : undefined
          }
        >
          {sessions.status === "loading" && <LoadingPanel label="Loading your browsers…" />}
          {sessions.error !== null && (
            <ProblemNotice problem={describeProblem(sessions.error, "Your browsers couldn't be loaded")} onRetry={sessions.reload} />
          )}
          {sessions.data && (
            <ul aria-label="Your signed-in browsers" className="divide-y divide-ink/[0.07]">
              {sessions.data.map((row) => (
                <li key={row.id} className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1 py-3">
                  <div className="min-w-0">
                    <p className="text-sm font-semibold">{row.device}</p>
                    <p className="mt-0.5 text-xs text-ink-soft">
                      Signed in {moment(row.created_at)} · seen {moment(row.last_seen_at)} · ends {moment(row.expires_at)}
                    </p>
                  </div>
                  {row.current && <Badge variant="solid">This browser</Badge>}
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
      <AlertDialog open={confirm !== null} onOpenChange={(open) => !open && !act.busy && setConfirm(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>
              {confirm?.kind === "disable" ? "Disable this admin?" : "Sign out your other browsers?"}
            </AlertDialogTitle>
            <AlertDialogDescription>
              {confirm?.kind === "disable"
                ? `${confirm.admin.email} is signed out everywhere and can't sign in. Only the server's admin CLI can let them back in.`
                : "Every other browser signed in to your admin account is signed out now. This one stays signed in."}
            </AlertDialogDescription>
          </AlertDialogHeader>
          {act.problem && <ProblemNotice problem={act.problem} />}
          <AlertDialogFooter>
            <AlertDialogCancel disabled={act.busy !== null}>Cancel</AlertDialogCancel>
            <Button
              variant={confirm?.kind === "disable" ? "destructive" : "default"}
              disabled={act.busy !== null}
              onClick={() => void run()}
            >
              {act.busy ? "Working…" : confirm?.kind === "disable" ? "Disable" : "Sign out the others"}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
