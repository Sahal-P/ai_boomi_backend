"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { SignInOptions } from "@/components/app-shell/sign-in-options";
import { BrandMark } from "@/components/brand";
import { MoneyScene } from "@/components/illustrations/scenes";
import { destinationTitle } from "@/lib/routes";

/** Sign-in is a yellow moment: flat sunflower, ink, the drawn money scene. */
export function HouseholdLogin({ next }: { next: string }) {
  const router = useRouter();
  const destination = destinationTitle(next);
  return (
    <main className="moment moment-page min-h-dvh">
      {/* Phones: intro, scene, options. Wider screens: intro and options beside the scene. */}
      <div className="mx-auto grid min-h-dvh max-w-6xl content-center gap-x-14 gap-y-7 px-5 py-10 sm:px-8 lg:grid-cols-2 lg:py-16">
        <div className="lg:col-start-1">
          <Link href="/" className="inline-flex items-center gap-2 text-[1.45rem] font-bold tracking-[-0.05em] text-ink">
            <BrandMark className="size-8" /> finboy
          </Link>
          <h1 id="login-title" className="mt-8 max-w-[13ch] text-[2.5rem] leading-[1.02] font-extrabold tracking-[-0.045em] sm:text-5xl">
            Your money, in your words
          </h1>
          <p className="mt-4 max-w-md text-base leading-relaxed text-sunflower-ink">
            {destination
              ? `Sign in or create your account — you'll go straight on to ${destination}.`
              : "Sign in or create your account in one tap. Your records stay private to your household."}
          </p>
        </div>
        <MoneyScene className="mx-auto w-full max-w-[16rem] self-center sm:max-w-sm lg:col-start-2 lg:row-span-2 lg:row-start-1 lg:max-w-none" />
        <section aria-labelledby="login-title" className="w-full max-w-md lg:col-start-1">
          <SignInOptions
            onSignedIn={() => {
              router.replace(next);
              router.refresh();
            }}
          />
          <p className="mt-6 text-xs leading-relaxed text-sunflower-ink">
            Just looking?{" "}
            <Link href="/demo" className="font-semibold text-ink underline underline-offset-4">
              View the sample household
            </Link>
            .
          </p>
        </section>
      </div>
    </main>
  );
}
