import Link from "next/link";
import type { ReactNode } from "react";

const navigation = [
  ["Dashboard", "/dashboard"],
  ["Transactions", "/transactions"],
  ["Review", "/review"],
  ["Assistant", "/assistant"],
  ["Connect", "/connect"],
  ["Privacy", "/privacy"],
] as const;

export default function AppLayout({ children }: { children: ReactNode }) {
  return (
    <div className="mx-auto min-h-screen max-w-6xl px-4 py-6 sm:px-8">
      <a href="#main-content" className="sr-only focus:not-sr-only focus:underline">
        Skip to content
      </a>
      <header className="mb-10 flex flex-wrap items-center gap-6 border-b pb-6">
        <Link href="/" className="text-xl font-semibold">FinBoy</Link>
        <nav aria-label="Main navigation">
          <ul className="flex flex-wrap gap-x-5 gap-y-3">
            {navigation.map(([label, href]) => (
              <li key={href}>
                <Link className="rounded-sm underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-4" href={href}>
                  {label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </header>
      <main id="main-content" tabIndex={-1}>{children}</main>
    </div>
  );
}
