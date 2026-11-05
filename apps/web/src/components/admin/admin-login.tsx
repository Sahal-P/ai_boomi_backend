"use client";

import { ShieldCheck } from "lucide-react";
import { useRouter } from "next/navigation";
import { useId, useState } from "react";
import { Brand } from "@/components/brand";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAdminSignIn } from "@/hooks/use-admin";
import { PASSWORD_PAGE } from "@/components/admin/admin-gate";

/** Operator sign-in: email and password only, on the app's own field and glass. */
export function AdminLogin({ next }: { next: string }) {
  const router = useRouter();
  const ids = useId();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const login = useAdminSignIn((session) => {
    router.replace(session.must_change_password ? PASSWORD_PAGE : next);
  });
  const failed = login.problem?.code === "admin_login_failed";
  return (
    <main className="bg-field grid min-h-dvh place-items-center px-4 py-10 sm:px-6">
      <div className="w-full max-w-md">
        <div className="flex items-center gap-2">
          <Brand href="/" />
          <span className="rounded-full bg-ink px-2 py-0.5 text-[11px] font-semibold text-white">Admin</span>
        </div>
        <section aria-labelledby={`${ids}-title`} className="surface mt-6 rounded-3xl p-6 sm:p-8">
          <h1 id={`${ids}-title`} className="text-[1.75rem] leading-tight font-medium tracking-[-0.025em]">
            Sign in to the admin panel
          </h1>
          <p className="mt-1.5 text-sm leading-relaxed text-ink-soft">
            For the people who run FinBoy. You&apos;ll see activity and settings, never a
            household&apos;s records or messages.
          </p>
          <form
            className="mt-6 space-y-4"
            onSubmit={(event) => {
              event.preventDefault();
              const typed = password;
              setPassword("");
              void login.submit(email.trim(), typed);
            }}
          >
            <div>
              <label htmlFor={`${ids}-email`} className="text-sm font-semibold">
                Email
              </label>
              <Input
                id={`${ids}-email`}
                type="email"
                autoComplete="username"
                inputMode="email"
                spellCheck={false}
                required
                maxLength={254}
                value={email}
                aria-invalid={failed || undefined}
                aria-describedby={login.problem ? `${ids}-problem` : undefined}
                onChange={(event) => setEmail(event.target.value)}
                className="mt-1.5"
              />
            </div>
            <div>
              <label htmlFor={`${ids}-password`} className="text-sm font-semibold">
                Password
              </label>
              <Input
                id={`${ids}-password`}
                type="password"
                autoComplete="current-password"
                required
                maxLength={256}
                value={password}
                aria-invalid={failed || undefined}
                aria-describedby={login.problem ? `${ids}-problem` : undefined}
                onChange={(event) => setPassword(event.target.value)}
                className="mt-1.5"
              />
            </div>
            {login.problem && <ProblemNotice id={`${ids}-problem`} problem={login.problem} />}
            <Button type="submit" size="lg" className="w-full" disabled={login.busy}>
              {login.busy ? "Signing in…" : "Sign in"}
            </Button>
          </form>
        </section>
        <p className="mt-4 flex items-start gap-2 px-1 text-xs leading-relaxed text-ink-soft">
          <ShieldCheck className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          Admin accounts are created on the server. Every sign-in and action is recorded in the
          audit log.
        </p>
      </div>
    </main>
  );
}
