"use client";

import { LockKeyhole } from "lucide-react";
import { Dialog } from "radix-ui";
import { useEffect, useId, useState } from "react";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useSignIn } from "@/hooks/use-household";
import { onSessionEvent } from "@/lib/session-events";

/**
 * Re-authenticates in place when a request reports an expired session, so the current page,
 * its filters and any unsaved draft stay in memory. Nothing is written to browser storage.
 */
export function SessionExpiredDialog() {
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState("");
  const errorId = useId();
  const login = useSignIn(() => setOpen(false));
  useEffect(() => onSessionEvent("expired", () => setOpen(true)), []);
  const here =
    typeof window === "undefined" ? "/dashboard" : `${window.location.pathname}${window.location.search}`;
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
          <form
            className="mt-5 space-y-4"
            onSubmit={(event) => {
              event.preventDefault();
              const submitted = password;
              setPassword("");
              void login.submit(submitted);
            }}
          >
            <div className="space-y-2">
              <label htmlFor="session-password" className="text-sm font-medium">
                Household password
              </label>
              <Input
                id="session-password"
                type="password"
                autoComplete="current-password"
                required
                maxLength={256}
                value={password}
                aria-invalid={login.problem?.code === "invalid_credentials" || undefined}
                aria-describedby={login.problem ? errorId : undefined}
                onChange={(event) => setPassword(event.target.value)}
              />
            </div>
            {login.problem && <ProblemNotice id={errorId} problem={login.problem} />}
            <div className="flex flex-wrap gap-2">
              <Button type="submit" disabled={login.busy}>
                {login.busy ? "Signing in…" : "Sign in"}
              </Button>
              <Dialog.Close asChild>
                <Button type="button" variant="ghost">
                  Not now
                </Button>
              </Dialog.Close>
            </div>
          </form>
          <p className="mt-5 text-xs leading-relaxed text-ink-soft">
            Prefer the full sign-in page?{" "}
            <a
              className="font-semibold text-ink underline underline-offset-4"
              href={`/login?next=${encodeURIComponent(here)}`}
            >
              Open it
            </a>{" "}
            — unsaved edits on this page will be lost.
          </p>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
