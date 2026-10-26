"use client";

import { X } from "lucide-react";
import { Dialog } from "radix-ui";
import { useState } from "react";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { LoadingPanel } from "@/components/feedback/states";
import { ExportButton } from "@/components/privacy/export-button";
import { Button } from "@/components/ui/button";
import { useAction } from "@/hooks/use-action";
import { useResource } from "@/hooks/use-resource";
import { disconnectConnection, type MailConnection } from "@/lib/api/mail";
import { deleteImported, previewDeletion, type DeletionPreview } from "@/lib/api/privacy";
import { formatDay } from "@/lib/dates";
import { describeProblem, isConflict } from "@/lib/messages";

const plural = (count: number, one: string, many: string) => `${count} ${count === 1 ? one : many}`;

function Impact({ preview }: { preview: DeletionPreview }) {
  const range =
    preview.first_received_at && preview.last_received_at
      ? `${formatDay(preview.first_received_at)} – ${formatDay(preview.last_received_at)}`
      : null;
  return (
    <div className="space-y-3 text-sm leading-relaxed">
      <div className="rounded-2xl bg-red-50 p-4 text-ink">
        <p className="font-semibold">Will be permanently deleted</p>
        <ul className="mt-1 list-disc space-y-0.5 pl-5">
          <li>
            {plural(preview.removed_transaction_count, "record", "records")} built from{" "}
            {plural(preview.source_count, "imported email", "imported emails")}
            {range ? ` received ${range}` : ""}
          </li>
          <li>{plural(preview.removed_obligation_count, "bill or obligation", "bills and obligations")}</li>
          <li>Their evidence snippets and the corrections you made to them</li>
        </ul>
      </div>
      <div className="rounded-2xl bg-ink/[0.04] p-4">
        <p className="font-semibold">Will stay</p>
        <ul className="mt-1 list-disc space-y-0.5 pl-5 text-ink-soft">
          <li>
            {plural(preview.retained_shared_transaction_count, "record", "records")} also supported by
            emails from another source — kept, but put on hold for review if their values came from
            the deleted emails
          </li>
          <li>{plural(preview.retained_shared_obligation_count, "obligation", "obligations")} shared with another source</li>
          <li>Your activity history (what happened and when, without contents)</li>
        </ul>
      </div>
      <p className="text-ink-soft">
        Private server backups can keep these structured records for up to{" "}
        {preview.backup_retention_days} days after deletion before they expire. Importing the same
        emails again can recreate records.
      </p>
    </div>
  );
}

/**
 * One deliberate confirmation with the exact scope shown first: what is removed, what stays and
 * backup retention. Disconnect (revoking Google access) is a separate choice.
 */
export function DeletionDialog({
  target,
  exportVersion,
  onClose,
  onDone,
}: {
  target: { kind: "delete" } | { kind: "disconnect"; connection: MailConnection } | null;
  exportVersion: string | null;
  onClose: () => void;
  onDone: (message: string) => void;
}) {
  const [alsoDelete, setAlsoDelete] = useState(false);
  const connectionId = target?.kind === "disconnect" ? target.connection.id : null;
  const wantsPreview = target?.kind === "delete" || (target?.kind === "disconnect" && alsoDelete);
  const preview = useResource(wantsPreview ? `deletion:${connectionId ?? "all"}` : null, (signal) =>
    previewDeletion(connectionId, signal),
  );
  const action = useAction();
  const [partial, setPartial] = useState(false);
  const data = preview.stale ? null : preview.data;

  async function confirm() {
    if (!target) return;
    if (wantsPreview && !data) return;
    setPartial(false);
    let deleted = false;
    const result = await action.run(
      "confirm",
      target.kind === "delete" ? "Nothing was deleted" : "Gmail wasn't disconnected",
      async () => {
        if (wantsPreview && data) {
          try {
            await deleteImported(data.version, connectionId);
            deleted = true;
          } catch (error) {
            if (isConflict(error)) preview.reload();
            throw error;
          }
        }
        if (target.kind === "disconnect") await disconnectConnection(target.connection.id);
        return true;
      },
    );
    if (!result) {
      if (deleted) setPartial(true);
      return;
    }
    setAlsoDelete(false);
    onDone(
      target.kind === "delete"
        ? `Deleted ${plural(data?.removed_transaction_count ?? 0, "record", "records")}. Your activity history was kept.`
        : wantsPreview
          ? `Gmail disconnected and ${plural(data?.removed_transaction_count ?? 0, "record", "records")} deleted.`
          : "Gmail disconnected. Your imported records were kept.",
    );
  }

  function close() {
    if (action.busy !== null) return;
    setAlsoDelete(false);
    setPartial(false);
    action.clear();
    onClose();
  }

  const title = target?.kind === "delete" ? "Delete imported records?" : "Disconnect Gmail?";
  const confirmLabel =
    target?.kind === "delete"
      ? `Delete ${data ? plural(data.removed_transaction_count, "record", "records") : "records"}`
      : wantsPreview
        ? `Delete ${data ? plural(data.removed_transaction_count, "record", "records") : "records"} and disconnect`
        : "Disconnect Gmail";

  return (
    <Dialog.Root open={target !== null} onOpenChange={(open) => !open && close()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-ink/20 backdrop-blur-sm" />
        <Dialog.Content className="fixed inset-x-0 bottom-0 z-50 max-h-[94dvh] overflow-y-auto rounded-t-3xl float-panel p-5 pb-8 sm:top-1/2 sm:bottom-auto sm:left-1/2 sm:max-h-[90dvh] sm:w-[calc(100%-2rem)] sm:max-w-lg sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-3xl sm:p-7">
          <div className="flex items-start justify-between gap-3">
            <Dialog.Title className="text-xl font-semibold">{title}</Dialog.Title>
            <Dialog.Close asChild>
              <Button variant="ghost" size="icon" aria-label="Close" disabled={action.busy !== null}>
                <X className="size-5" aria-hidden="true" />
              </Button>
            </Dialog.Close>
          </div>
          <Dialog.Description className="mt-2 text-sm leading-relaxed text-ink-soft">
            {target?.kind === "disconnect"
              ? `FinBoy will revoke its read-only access to ${target.connection.account_email_masked} and erase the saved Google token. Choose what happens to records already imported.`
              : "Review exactly what changes before you decide. This can't be undone."}
          </Dialog.Description>

          {target?.kind === "disconnect" && (
            <fieldset className="mt-4 space-y-2 text-sm" disabled={action.busy !== null}>
              <legend className="mb-1 font-semibold">Records already imported</legend>
              <label className="flex min-h-11 items-center gap-3 rounded-xl border px-3">
                <input type="radio" name="disconnect-data" checked={!alsoDelete} onChange={() => setAlsoDelete(false)} className="accent-[var(--violet)]" />
                Keep them in my records
              </label>
              <label className="flex min-h-11 items-center gap-3 rounded-xl border px-3">
                <input type="radio" name="disconnect-data" checked={alsoDelete} onChange={() => setAlsoDelete(true)} className="accent-[var(--violet)]" />
                Also delete records imported from this account
              </label>
            </fieldset>
          )}

          {wantsPreview && (
            <div className="mt-4">
              {preview.status === "loading" && <LoadingPanel className="shadow-none" label="Working out exactly what would be deleted…" />}
              {preview.error !== null && (
                <ProblemNotice problem={describeProblem(preview.error, "The deletion preview couldn't be loaded")} onRetry={preview.reload} />
              )}
              {data && <Impact preview={data} />}
              {data && data.removed_transaction_count > 0 && (
                <div className="mt-4 rounded-2xl border p-4">
                  <p className="text-sm font-semibold">Keep a copy first?</p>
                  <p className="mt-1 text-xs text-ink-soft">Your structured records and corrections, without email contents.</p>
                  <div className="mt-3">
                    <ExportButton version={exportVersion} />
                  </div>
                </div>
              )}
            </div>
          )}

          {action.problem && (
            <ProblemNotice className="mt-4" problem={action.problem}>
              {isConflict(action.lastError) && <p className="mt-1">The preview above has been refreshed — check it again before deciding.</p>}
              {partial && (
                <p className="mt-1">The records were deleted, but Google access wasn&apos;t revoked. Try Disconnect again.</p>
              )}
            </ProblemNotice>
          )}

          <div className="mt-6 flex flex-wrap justify-end gap-2">
            <Dialog.Close asChild>
              <Button variant="outline" disabled={action.busy !== null}>
                Cancel
              </Button>
            </Dialog.Close>
            <Button
              variant="destructive"
              disabled={action.busy !== null || (wantsPreview && (!data || preview.status !== "ready"))}
              onClick={() => void confirm()}
            >
              {action.busy ? "Working…" : confirmLabel}
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
