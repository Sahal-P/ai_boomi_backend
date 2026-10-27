import Link from "next/link";
import type { ReactNode } from "react";
import { BrandMark } from "@/components/brand";

/** Public legal pages: plain words, one column, readable at 320 px. */
export function LegalPage({
  title,
  updated,
  children,
}: {
  title: string;
  updated: string;
  children: ReactNode;
}) {
  return (
    <main className="bg-field min-h-dvh px-4 py-10 sm:px-8">
      <article className="surface mx-auto max-w-3xl rounded-3xl p-6 leading-relaxed sm:p-10 [&_h2]:mt-8 [&_h2]:text-lg [&_h2]:font-semibold [&_li]:mt-1 [&_p]:mt-3 [&_ul]:mt-3 [&_ul]:list-disc [&_ul]:pl-5">
        <Link href="/" className="inline-flex items-center gap-2 text-xl font-bold tracking-[-0.05em] text-ink">
          <BrandMark className="size-7" /> finboy
        </Link>
        <h1 className="mt-8 text-3xl font-extrabold tracking-[-0.03em] sm:text-4xl">{title}</h1>
        <p className="text-sm text-ink-soft">Last updated {updated}. Draft for legal review.</p>
        {children}
        <p className="mt-10 border-t border-ink/10 pt-6 text-sm text-ink-soft">
          <Link href="/privacy-policy" className="font-semibold underline underline-offset-4">
            Privacy Policy
          </Link>{" "}
          ·{" "}
          <Link href="/terms" className="font-semibold underline underline-offset-4">
            Terms
          </Link>{" "}
          ·{" "}
          <Link href="/login" className="font-semibold underline underline-offset-4">
            Sign in
          </Link>
        </p>
      </article>
    </main>
  );
}
