"use client";

import { ChevronsRight, LockKeyhole } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useId, useState } from "react";
import { BrandMark } from "@/components/brand";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { MoneyScene } from "@/components/illustrations/scenes";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useSignIn } from "@/hooks/use-household";
import { destinationTitle } from "@/lib/routes";

/** Sign-in is a yellow moment: flat sunflower, ink, the drawn money scene. */
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
    <main className="moment moment-page min-h-dvh">
      {/* Phones: intro, scene, form. Wider screens: intro and form beside the scene. */}
      <div className="mx-auto grid min-h-dvh max-w-6xl content-center gap-x-14 gap-y-7 px-5 py-10 sm:px-8 lg:grid-cols-2 lg:py-16">
        <div className="lg:col-start-1">
          <Link href="/" className="inline-flex items-center gap-2 text-[1.45rem] font-bold tracking-[-0.05em] text-violet-deep">
            <BrandMark className="size-8" /> finboy
          </Link>
          <h1 id="login-title" className="mt-8 max-w-[12ch] text-[2.5rem] leading-[1.02] font-extrabold tracking-[-0.045em] sm:text-5xl">
            Sign in to your household
          </h1>
          <p className="mt-4 max-w-md text-base leading-relaxed text-sunflower-ink">
            {destination
              ? `After signing in you'll go straight back to ${destination}.`
              : "Your records stay private to this household."}
          </p>
        </div>
        <MoneyScene className="mx-auto w-full max-w-[19rem] self-center sm:max-w-sm lg:col-start-2 lg:row-span-2 lg:row-start-1 lg:max-w-none" />
        <section aria-labelledby="login-title" className="w-full max-w-md lg:col-start-1">
          <form
            className="space-y-4"
            onSubmit={(event) => {
              event.preventDefault();
              const submitted = password;
              setPassword("");
              void login.submit(submitted);
            }}
          >
            <div className="space-y-2">
              <label htmlFor="household-password" className="text-sm font-semibold">
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
                className="h-12 rounded-2xl border-2 border-ink bg-white text-base"
              />
            </div>
            {login.problem && <ProblemNotice id={errorId} problem={login.problem} />}
            <Button type="submit" size="lg" className="relative h-14 w-full text-base" disabled={login.busy}>
              {/* The reference's chevron capsule: decoration on an ordinary button, not a swipe. */}
              <span aria-hidden="true" className="absolute top-1 bottom-1 left-1 grid w-16 place-items-center rounded-full bg-white text-ink">
                <ChevronsRight className="size-5" />
              </span>
              {login.busy ? "Signing in…" : "Sign in"}
            </Button>
          </form>
          <div className="mt-7 flex gap-3 rounded-2xl bg-white/55 p-4 text-xs leading-relaxed">
            <LockKeyhole className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            <p>
              FinBoy is a private space for one household — there&apos;s no public sign-up or
              password reset. Ask the person who set it up for the password. Want to look around
              first?{" "}
              <Link href="/demo" className="font-semibold underline underline-offset-4">
                View the sample data
              </Link>
              .
            </p>
          </div>
        </section>
      </div>
    </main>
  );
}
