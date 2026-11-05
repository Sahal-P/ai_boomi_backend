"use client";

import { useRouter } from "next/navigation";
import { useId, useState } from "react";
import { useAdminAccess } from "@/components/admin/admin-gate";
import { PageHeader } from "@/components/app-shell/page-header";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAction } from "@/hooks/use-action";
import { changeAdminPassword } from "@/lib/api/admin";

/** Change your own password; a temporary one must be changed before anything else opens. */
export function PasswordScreen() {
  const { email, mustChangePassword, passwordChanged } = useAdminAccess();
  const router = useRouter();
  const ids = useId();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [repeat, setRepeat] = useState("");
  const [done, setDone] = useState(false);
  const change = useAction();
  const short = next.length > 0 && next.length < 12;
  const mismatch = repeat.length > 0 && next !== repeat;
  const ready = current.length > 0 && next.length >= 12 && next === repeat;

  async function submit() {
    if (!ready) return;
    const typed = current;
    setCurrent("");
    setDone(false);
    const result = await change.run("password", "Your password wasn't changed", () => changeAdminPassword(typed, next));
    if (!result) return;
    setNext("");
    setRepeat("");
    setDone(true);
    const first = mustChangePassword;
    passwordChanged();
    if (first) router.replace("/admin");
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title={mustChangePassword ? "Choose your own password" : "Change your password"}
        description={
          mustChangePassword
            ? "You signed in with a temporary password. Choose your own to open the rest of the panel."
            : "Your other signed-in browsers are signed out when it changes."
        }
      />
      <section aria-label="Password" className="surface max-w-xl rounded-3xl p-5 sm:p-6">
        <form
          className="space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            void submit();
          }}
        >
          {/* For password managers: the account this password belongs to. */}
          <input type="email" autoComplete="username" value={email} readOnly hidden />
          <p className="text-sm">
            <span className="text-ink-soft">Account </span>
            <span className="font-semibold break-all">{email}</span>
          </p>
          <div>
            <label htmlFor={`${ids}-current`} className="text-sm font-semibold">
              {mustChangePassword ? "Temporary password" : "Current password"}
            </label>
            <Input
              id={`${ids}-current`}
              type="password"
              autoComplete="current-password"
              required
              maxLength={256}
              value={current}
              onChange={(event) => setCurrent(event.target.value)}
              className="mt-1.5"
            />
          </div>
          <div>
            <label htmlFor={`${ids}-next`} className="text-sm font-semibold">
              New password
            </label>
            <Input
              id={`${ids}-next`}
              type="password"
              autoComplete="new-password"
              required
              minLength={12}
              maxLength={256}
              value={next}
              aria-invalid={short || undefined}
              aria-describedby={`${ids}-next-hint`}
              onChange={(event) => setNext(event.target.value)}
              className="mt-1.5"
            />
            <p id={`${ids}-next-hint`} className={short ? "mt-1 text-xs font-semibold text-ink" : "mt-1 text-xs text-ink-soft"}>
              12 to 256 characters, not your email. A short phrase you don&apos;t use anywhere else works well.
            </p>
          </div>
          <div>
            <label htmlFor={`${ids}-repeat`} className="text-sm font-semibold">
              Repeat the new password
            </label>
            <Input
              id={`${ids}-repeat`}
              type="password"
              autoComplete="new-password"
              required
              maxLength={256}
              value={repeat}
              aria-invalid={mismatch || undefined}
              aria-describedby={mismatch ? `${ids}-repeat-hint` : undefined}
              onChange={(event) => setRepeat(event.target.value)}
              className="mt-1.5"
            />
            {mismatch && (
              <p id={`${ids}-repeat-hint`} className="mt-1 text-xs font-semibold text-ink">
                The two new passwords don&apos;t match yet.
              </p>
            )}
          </div>
          {change.problem && <ProblemNotice problem={change.problem} />}
          <div role="status" aria-live="polite" className="text-sm font-medium">
            {done && "Password changed. Your other browsers are signed out."}
          </div>
          <Button type="submit" disabled={!ready || change.busy !== null}>
            {change.busy ? "Saving…" : "Save new password"}
          </Button>
        </form>
      </section>
    </div>
  );
}
