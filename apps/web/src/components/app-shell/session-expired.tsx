"use client";

import { LockKeyhole } from "lucide-react";
import { Dialog } from "radix-ui";
import { useEffect, useState } from "react";
import { SignInOptions } from "@/components/app-shell/sign-in-options";
import { Button } from "@/components/ui/button";
import { emitSessionEvent, onSessionEvent } from "@/lib/session-events";

/**
 * Re-authenticates in place when a request reports an expired session, so the current page,
 * its filters and any unsaved draft stay in memory. Nothing is written to browser storage.
 */
export function SessionExpiredDialog() {
  const [open, setOpen] = useState(false);
  useEffect(() => onSessionEvent("expired", () => setOpen(true)), []);
  return (
    <Dialog.Root open={open} onOpenChange={setOpen}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-[60] bg-ink/20 backdrop-blur-sm" />
        <Dialog.Content
          aria-describedby="session-expired-description"
          className="fixed top-1/2 left-1/2 z-[60] max-h-[90dvh] w-[calc(100%-1.5rem)] max-w-md -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-3xl float-panel p-6 sm:p-7"
        >
          <LockKeyhole className="size-6 text-ink" aria-hidden="true" />
          <Dialog.Title className="mt-3 text-xl font-semibold">Sign in to continue</Dialog.Title>
          <Dialog.Description
            id="session-expired-description"
            className="mt-2 text-sm leading-relaxed text-ink-soft"
          >
            Your private session ended. Sign in again here — this page, its filters and any
            unsaved edits stay as they are. Retry your last action afterwards.
          </Dialog.Description>
          {open ? (
            <div className="mt-5">
              <SignInOptions
                onSignedIn={() => {
                  emitSessionEvent("restored");
                  setOpen(false);
                }}
              />
            </div>
          ) : null}
          <Dialog.Close asChild>
            <Button type="button" variant="ghost" className="mt-4">
              Not now
            </Button>
          </Dialog.Close>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
