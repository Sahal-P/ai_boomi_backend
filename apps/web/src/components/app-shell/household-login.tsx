"use client";

import { LockKeyhole } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useState } from "react";
import { BrandMark } from "@/components/brand";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useSignIn } from "@/hooks/use-household";
import { destinationTitle } from "@/lib/routes";

export function HouseholdLogin({ next }: { next: string }) {
  const router = useRouter();
  const [password, setPassword] = useState("");
  const errorId = useId();
  const login = useSignIn(() => {
    router.replace(next);
    router.refresh();
  });
  const destination = destinationTitle(next);
  const wrongPassword = login.problem?.code === "invalid_credentials";
  return (
    <main className="grid min-h-dvh place-items-center bg-aurora p-4 sm:p-6">
      <section
        className="surface w-full max-w-md rounded-3xl p-6 sm:p-8"
        aria-labelledby="login-title"
      >
        <Link href="/" className="inline-flex items-center gap-2 text-sm font-semibold text-ink">
          <BrandMark className="size-7" /> FinBoy
        </Link>
        <h1 id="login-title" className="mt-6 text-2xl font-semibold tracking-tight">
          Sign in to your household
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-ink-soft">
          {destination
            ? `After signing in you'll go straight back to ${destination}.`
            : "Your records stay private to this household."}
        </p>
        <form
          className="mt-7 space-y-4"
          onSubmit={(event) => {
            event.preventDefault();
            const submitted = password;
            setPassword("");
            void login.submit(submitted);
          }}
        >
          <div className="space-y-2">
            <label htmlFor="household-password" className="text-sm font-medium">
              Household password
            </label>
            <Input
              id="household-password"
              type="password"
              name="password"
              autoComplete="current-password"
              required
              maxLength={256}
              value={password}
              aria-invalid={wrongPassword || undefined}
              aria-describedby={login.problem ? errorId : undefined}
              onChange={(event) => setPassword(event.target.value)}
            />
          </div>
          {login.problem && <ProblemNotice id={errorId} problem={login.problem} />}
          <Button type="submit" className="w-full" disabled={login.busy}>
            {login.busy ? "Signing in…" : "Sign in"}
          </Button>
        </form>
        <div className="mt-7 flex gap-3 rounded-2xl bg-canvas p-4 text-xs leading-relaxed text-ink-soft">
          <LockKeyhole className="mt-0.5 size-4 shrink-0 text-violet-deep" aria-hidden="true" />
          <p>
            FinBoy is a private space for one household — there&apos;s no public sign-up or
            password reset. Ask the person who set it up for the password. Want to look around
            first?{" "}
            <Link href="/demo" className="font-semibold text-violet-deep underline underline-offset-4">
              View the sample data
            </Link>
            .
          </p>
        </div>
      </section>
    </main>
  );
}
