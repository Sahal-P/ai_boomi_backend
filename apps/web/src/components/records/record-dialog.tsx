"use client";

import { X } from "lucide-react";
import { Dialog } from "radix-ui";
import { useState, type ReactNode } from "react";
import { RecordDecision } from "@/components/records/record-decision";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import type { DecisionOutcome } from "@/hooks/use-record";
import { writeDraft } from "@/lib/drafts";
import { setUnsaved } from "@/lib/unsaved-work";

/**
 * A URL-selected record. Escape, outside click and Close ask before discarding a dirty draft;
 * focus returns to the record that opened it (or the list when it has gone).
 */
export function RecordDialog({
  id,
  onClose,
  onDecided,
  focusFallback,
  header,
  footer,
  showUndo = true,
}: {
  id: string | null;
  onClose: () => void;
  onDecided?: (outcome: DecisionOutcome) => void;
  focusFallback?: () => HTMLElement | null;
  header?: ReactNode;
  footer?: ReactNode;
  showUndo?: boolean;
}) {
  const [dirty, setDirty] = useState(false);
  const [confirming, setConfirming] = useState(false);
  // The record that opened the dialog, kept after close so focus can return to it.
  const [origin, setOrigin] = useState<string | null>(id);
  if (id && id !== origin) setOrigin(id);

  function requestClose() {
    if (dirty) setConfirming(true);
    else onClose();
  }

  return (
    <>
      <Dialog.Root open={id !== null} onOpenChange={(open) => !open && requestClose()}>
        <Dialog.Portal>
          <Dialog.Overlay className="fixed inset-0 z-50 bg-ink/20 backdrop-blur-sm" />
          <Dialog.Content
            aria-describedby={undefined}
            // Radix focuses Close first; the record heading takes focus once evidence loads.
            onCloseAutoFocus={(event) => {
              event.preventDefault();
              const row = origin
                ? document.querySelector<HTMLElement>(`[data-record-id="${CSS.escape(origin)}"]`)
                : null;
              (row ?? focusFallback?.())?.focus();
            }}
            className="fixed inset-x-0 bottom-0 z-50 max-h-[94dvh] overflow-y-auto rounded-t-3xl float-panel p-5 pb-8 sm:top-1/2 sm:bottom-auto sm:left-1/2 sm:max-h-[90dvh] sm:w-[calc(100%-2rem)] sm:max-w-2xl sm:-translate-x-1/2 sm:-translate-y-1/2 sm:rounded-3xl sm:p-8"
          >
            <Dialog.Title className="sr-only">Record details</Dialog.Title>
            <div className="mb-2 flex justify-end">
              <Button variant="ghost" size="icon" aria-label="Close record" onClick={requestClose}>
                <X className="size-5" aria-hidden="true" />
              </Button>
            </div>
            {header}
            {id && (
              <RecordDecision
                key={id}
                id={id}
                focusOnLoad
                showUndo={showUndo}
                onDirtyChange={setDirty}
                {...(onDecided ? { onDecided } : {})}
              />
            )}
            {footer}
          </Dialog.Content>
        </Dialog.Portal>
      </Dialog.Root>
      <AlertDialog open={confirming} onOpenChange={setConfirming}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Discard your changes?</AlertDialogTitle>
            <AlertDialogDescription>
              You edited this record but didn&apos;t save. Closing discards those edits.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep editing</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => {
                if (id) {
                  writeDraft(id, null);
                  setUnsaved(`record:${id}`, false);
                }
                setDirty(false);
                onClose();
              }}
            >
              Discard changes
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
