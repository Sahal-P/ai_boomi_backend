import Link from "next/link";
import type { ReactNode } from "react";
import { Brand } from "@/components/brand";

const PAGES = [
  { href: "/pricing", label: "Pricing" },
  { href: "/terms", label: "Terms" },
  { href: "/privacy-policy", label: "Privacy Policy" },
  { href: "/refund-policy", label: "Refunds" },
  { href: "/contact", label: "Contact" },
  { href: "/login", label: "Sign in" },
] as const;

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
        <Brand />
        <h1 className="mt-8 text-3xl font-extrabold tracking-[-0.03em] sm:text-4xl">{title}</h1>
        <p className="text-sm text-ink-soft">Last updated {updated}. Draft for legal review.</p>
        {children}
        <nav
          aria-label="FinBoy pages"
          className="mt-10 flex flex-wrap gap-x-5 gap-y-2 border-t border-ink/10 pt-6 text-sm text-ink-soft"
        >
          {PAGES.map((page) => (
            <Link key={page.href} href={page.href} className="font-semibold underline underline-offset-4">
              {page.label}
            </Link>
          ))}
        </nav>
      </article>
    </main>
  );
}
