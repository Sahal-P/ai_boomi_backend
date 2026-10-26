import type { Metadata } from "next";
import Link from "next/link";
import { Brand } from "@/components/brand";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = { title: "Page not found" };

export default function NotFound() {
  return (
    <main className="bg-field grid min-h-dvh place-items-center p-6">
      <section className="surface w-full max-w-md rounded-3xl p-6 sm:p-8">
        <Brand />
        <h1 className="mt-6 text-2xl font-medium tracking-[-0.025em]">That page doesn&apos;t exist</h1>
        <p className="mt-2 text-sm leading-relaxed text-ink-soft">
          The link may be old or mistyped. Nothing in your records was changed.
        </p>
        <div className="mt-5 flex flex-wrap gap-2">
          <Button asChild>
            <Link href="/dashboard">Go to your overview</Link>
          </Button>
          <Button asChild variant="ghost">
            <Link href="/">FinBoy home</Link>
          </Button>
        </div>
      </section>
    </main>
  );
}
