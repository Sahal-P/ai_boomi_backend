import Link from "next/link";
import { Dialog } from "radix-ui";
import { Mail, Pause, Play, RefreshCw, ShieldCheck, Trash2, Unplug, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import type { AuditEvent, MailConnection } from "@/lib/api/mail";
import { MailAlert, MailFrame } from "./mail-frame";

export type PrivacyAction = "pause" | "resume" | "sync" | "disconnect" | "delete";
type Props = {
  connections: MailConnection[] | null; events: AuditEvent[]; error: string | null;
  notice: string | null; busy: boolean; onRetry: () => void;
  onAction: (action: PrivacyAction, connection?: MailConnection, deleteData?: boolean) => Promise<boolean>;
  dialog: MailConnection | "delete" | null; onDialog: (value: MailConnection | "delete" | null) => void;
  deleteWithDisconnect: boolean; onDeleteChoice: (value: boolean) => void;
};

function timestamp(value: string | null) {
  return value ? new Intl.DateTimeFormat("en-IN", { dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Kolkata" }).format(new Date(value)) : "Not scanned yet";
}
const eventLabels: Record<string, string> = {
  "gmail.connected": "Gmail connected", "gmail.sync_requested": "Email scan requested",
  "gmail.paused": "Email imports paused", "gmail.resumed": "Email imports resumed",
  "gmail.revoked": "Gmail access revoked", "gmail.revoke_failed": "Gmail disconnect could not finish",
  "gmail.reconnect_required": "Gmail reconnect required", "import.started": "Import started",
  "import.completed": "Import completed", "import.failed": "Import stopped", "data.deleted": "Imported data deleted",
  "transaction.corrected": "Transaction corrected", "transaction.merged": "Duplicate merged",
};

export function PrivacyScreen(props: Props) {
  const { connections, events, error, notice, busy, onAction, dialog, onDialog } = props;
  return <MailFrame eyebrow="Your data. Your decisions." title="Trust starts with control."
    description="See what’s connected, pause email imports, or remove imported records. Every important action leaves a simple audit trail.">
    {error && <MailAlert message={error} onRetry={props.onRetry} />}
    {notice && <p role="status" className="mb-5 rounded-xl border bg-secondary p-4 text-sm text-primary">{notice}</p>}
    <div className="grid items-start gap-6 lg:grid-cols-[1.4fr_1fr]">
      <div className="space-y-6">
        <section className="rounded-2xl border bg-card p-6" aria-busy={connections === null && !error}>
          <h2 className="mb-5 text-lg font-medium">Connected accounts</h2>
          {connections === null ? <p role="status" className="text-sm text-muted-foreground">{error ? "Accounts unavailable. Try again when the API is connected." : "Loading your connections…"}</p>
            : !connections.length ? <p className="text-sm text-muted-foreground">No Gmail account connected. <Link href="/connect" className="font-medium text-primary underline">Choose an import mode</Link></p>
            : <ul className="space-y-5">{connections.map((connection) => <li key={connection.id} className="rounded-xl border p-4">
              <div className="flex items-start gap-3"><Mail className="mt-1 size-5 shrink-0 text-primary" /><div className="min-w-0 flex-1">
                <p className="break-all font-medium">{connection.account_email_masked}</p>
                <p className="mt-1 text-xs text-muted-foreground">Gmail · <span className="capitalize">{connection.status}</span></p>
                <p className="mt-2 text-xs text-muted-foreground">Last scan: {timestamp(connection.last_synced_at)} IST</p>
              </div></div>
              {connection.status === "error" && <p className="mt-3 text-sm text-amber-800">Google access needs attention. <Link href="/connect" className="underline">Reconnect Gmail</Link></p>}
              {connection.status !== "revoked" && <div className="mt-4 flex flex-wrap gap-2">
                {connection.status === "active" && <><Button variant="outline" disabled={busy || !!error} onClick={() => void onAction("sync", connection)}><RefreshCw /> Scan now</Button><Button variant="outline" disabled={busy || !!error} onClick={() => void onAction("pause", connection)}><Pause /> Pause</Button></>}
                {connection.status === "paused" && <Button variant="outline" disabled={busy || !!error} onClick={() => void onAction("resume", connection)}><Play /> Resume</Button>}
                <Button variant="ghost" disabled={busy || !!error} onClick={() => onDialog(connection)}><Unplug /> Disconnect</Button>
              </div>}
            </li>)}</ul>}
          <p className="mt-5 text-xs leading-relaxed text-muted-foreground">Pause stops imports. Disconnect revokes Google access. Testing-mode access expires after 7 days; reconnect before the demo.</p>
        </section>
        <section className="rounded-2xl border bg-card p-6">
          <h2 className="text-lg font-medium">Delete imported records</h2>
          <p className="mt-3 mb-5 text-sm leading-relaxed text-muted-foreground">Remove email-derived transactions, evidence, and commitments. Audit history stays. This cannot be undone; importing the emails again can recreate records.</p>
          <Button variant="destructive" disabled={busy || !!error || connections === null} onClick={() => onDialog("delete")}><Trash2 /> Delete imported data</Button>
        </section>
        <section className="rounded-2xl border bg-card p-6">
          <h2 className="mb-5 text-lg font-medium">Activity & audit trail</h2>
          {!events.length ? <p className="text-sm text-muted-foreground">{connections === null ? "Waiting for audit history…" : "No activity yet."}</p> : <ol className="max-h-80 space-y-4 overflow-auto">
            {events.map((event) => <li key={event.id} className="border-l-2 pl-4"><p className="text-sm">{eventLabels[event.event_type] ?? "Account activity"}</p><p className="mt-1 text-xs text-muted-foreground">{timestamp(event.created_at)} IST</p></li>)}
          </ol>}
        </section>
      </div>
      <aside className="rounded-2xl border bg-secondary/60 p-6 text-sm leading-relaxed">
        <ShieldCheck className="mb-4 size-7 text-primary" />
        <h2 className="text-lg font-medium">A few clear promises</h2>
        <h3 className="mt-6 font-medium">What stays</h3>
        <p className="mt-2 text-muted-foreground">Masked account details, message identifiers and hashes, structured financial records, and evidence snippets of up to 80 characters per field. Gmail refresh tokens are encrypted.</p>
        <h3 className="mt-6 font-medium">What doesn’t stay</h3>
        <p className="mt-2 text-muted-foreground">Raw email bodies, uploaded .eml files, full account email addresses, OAuth codes, and access tokens are never stored in the database. Access tokens live only in memory.</p>
        <h3 className="mt-6 font-medium">Your emails are not training data</h3>
        <p className="mt-2 text-muted-foreground">Financial emails are never used to train models. Relevant content may be processed by the backend’s extraction provider to create structured records.</p>
        <p className="mt-6 border-t pt-5 text-muted-foreground">FinBoy’s Gmail access is read only. It cannot send, edit, or delete messages in your inbox.</p>
      </aside>
    </div>
    <Dialog.Root open={dialog !== null} onOpenChange={(open) => { if (!open && !busy) onDialog(null); }}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/40" />
        <Dialog.Content className="fixed top-1/2 left-1/2 z-50 max-h-[90dvh] w-[calc(100%-2rem)] max-w-md -translate-x-1/2 -translate-y-1/2 overflow-auto rounded-2xl border bg-card p-6 shadow-xl">
          <Dialog.Title className="pr-6 text-xl font-medium">{dialog === "delete" ? "Delete imported records?" : "Disconnect Gmail?"}</Dialog.Title>
          <Dialog.Description className="mt-3 text-sm leading-relaxed text-muted-foreground">{dialog === "delete" ? "Email-derived records and evidence will be permanently removed. Your audit trail will stay. Gmail will remain connected; use Disconnect to revoke its access." : "FinBoy will revoke Google access and erase the saved refresh token. Choose what happens to the records already imported."}</Dialog.Description>
          {dialog && dialog !== "delete" && <fieldset className="mt-5 space-y-3 text-sm">
            <legend className="mb-2 font-medium">Imported records</legend>
            <label className="flex items-center gap-3 rounded-lg border p-3"><input type="radio" name="disconnect-data" checked={!props.deleteWithDisconnect} onChange={() => props.onDeleteChoice(false)} disabled={busy} /> Keep my ledger</label>
            <label className="flex items-center gap-3 rounded-lg border p-3"><input type="radio" name="disconnect-data" checked={props.deleteWithDisconnect} onChange={() => props.onDeleteChoice(true)} disabled={busy} /> Delete imported records for this account</label>
          </fieldset>}
          {error && <p role="alert" className="mt-4 text-sm text-destructive">{error}</p>}
          <div className="mt-6 flex flex-wrap justify-end gap-3">
            <Button variant="outline" disabled={busy} onClick={() => onDialog(null)}>Cancel</Button>
            <Button variant="destructive" disabled={busy} onClick={() => {
              if (!dialog) return;
              void onAction(dialog === "delete" ? "delete" : "disconnect", dialog === "delete" ? undefined : dialog, props.deleteWithDisconnect).then((success) => { if (success) onDialog(null); });
            }}>{busy ? "Working…" : dialog === "delete" ? "Delete imported data" : "Disconnect Gmail"}</Button>
          </div>
          <Dialog.Close asChild><button type="button" aria-label="Close dialog" disabled={busy} className="absolute top-5 right-5 text-muted-foreground"><X className="size-5" /></button></Dialog.Close>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  </MailFrame>;
}
