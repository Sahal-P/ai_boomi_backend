import { ArrowRight, FileUp, Inbox, LockKeyhole, Mail } from "lucide-react";
import { Button } from "@/components/ui/button";
import { MailAlert, MailFrame } from "./mail-frame";

export function ConnectScreen({ gmailUrl, error, busy, onDemo, onUpload }: {
  gmailUrl: string; error: string | null; busy: boolean;
  onDemo: () => void; onUpload: (files: File[]) => void;
}) {
  return <MailFrame eyebrow="A little clarity starts here" title="Your money already leaves a trail."
    description="Bank alerts, receipts, and bills are already in your inbox. Let FinBoy turn that trail into a clearer picture of your money — with you in control.">
    {error && <MailAlert message={error} />}
    <div className="grid gap-4 md:grid-cols-3" aria-busy={busy}>
      <article className="flex flex-col rounded-2xl border border-primary/30 bg-card p-6 shadow-sm">
        <Mail className="mb-8 size-7 text-primary" aria-hidden="true" />
        <p className="eyebrow uppercase text-primary">Your inbox, read only</p>
        <h2 className="mt-2 text-xl font-medium">Connect Gmail</h2>
        <p className="mt-3 mb-7 flex-1 text-sm leading-relaxed text-muted-foreground">Scan possible financial emails from the last 30 days. FinBoy cannot send, edit, or delete your emails.</p>
        <Button asChild className="h-11 w-full"><a href={gmailUrl}>Connect Gmail <ArrowRight className="size-4" /></a></Button>
      </article>
      <article className="flex flex-col rounded-2xl border bg-card p-6">
        <FileUp className="mb-8 size-7 text-primary" aria-hidden="true" />
        <p className="eyebrow uppercase text-muted-foreground">Choose what you share</p>
        <h2 className="mt-2 text-xl font-medium">Upload emails</h2>
        <p className="mt-3 mb-7 flex-1 text-sm leading-relaxed text-muted-foreground">Import saved .eml files without connecting an account. Up to 50 files, 2 MB each. Raw emails are processed in memory.</p>
        <label className="text-sm font-medium" htmlFor="eml-files">Select .eml files</label>
        <input id="eml-files" type="file" multiple accept=".eml,message/rfc822" disabled={busy}
          className="mt-2 w-full rounded-lg border bg-background p-2 text-xs file:mr-2 file:rounded file:border-0 file:bg-secondary file:p-2 file:text-primary focus-visible:outline-2 focus-visible:outline-primary"
          onChange={(event) => { const files = Array.from(event.target.files ?? []); if (files.length) onUpload(files); event.target.value = ""; }} />
      </article>
      <article className="flex flex-col rounded-2xl border bg-secondary/50 p-6">
        <Inbox className="mb-8 size-7 text-primary" aria-hidden="true" />
        <p className="eyebrow uppercase text-muted-foreground">Take a look around</p>
        <h2 className="mt-2 text-xl font-medium">Try the demo</h2>
        <p className="mt-3 mb-7 flex-1 text-sm leading-relaxed text-muted-foreground">Explore Arun’s synthetic mailbox: salary, everyday spending, bills, and a few items that need a human look.</p>
        <Button variant="outline" className="h-11 w-full" disabled={busy} onClick={onDemo}>{busy ? "Starting import…" : "Load demo mailbox"}<ArrowRight className="size-4" /></Button>
      </article>
    </div>
    <p role="status" className="mt-4 text-sm text-primary">{busy ? "Preparing your import. Please keep this page open…" : ""}</p>
    <div className="mt-6 flex gap-3 rounded-xl border p-5 text-sm leading-relaxed text-muted-foreground">
      <LockKeyhole className="mt-0.5 size-5 shrink-0 text-primary" aria-hidden="true" />
      <p>Raw email bodies are never stored. Financial emails are never used to train models. Pause, disconnect, or delete imported records at any time from Privacy.</p>
    </div>
  </MailFrame>;
}
