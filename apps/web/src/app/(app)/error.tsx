"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";

/** Route-level recovery for an unexpected rendering failure; no error details are shown or logged. */
export default function AppError({ retry }: { error: unknown; retry: () => void }) {
  return (
    <div role="alert" className="surface max-w-xl rounded-3xl p-6 sm:p-8">
      <h1 className="text-2xl font-semibold tracking-tight">This page couldn&apos;t be shown</h1>
      <p className="mt-2 text-sm leading-relaxed text-ink-soft">
        Something unexpected happened while displaying it. Nothing in your records was changed.
      </p>
      <div className="mt-5 flex flex-wrap gap-2">
        <Button onClick={retry}>Try again</Button>
        <Button asChild variant="ghost">
          <Link href="/dashboard">Go to Home</Link>
        </Button>
      </div>
    </div>
  );
}
