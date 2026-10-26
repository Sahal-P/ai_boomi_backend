import { LoaderCircle } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/** Loading placeholder announced politely once; keeps layout stable without fake data. */
export function LoadingPanel({ label, className }: { label: string; className?: string }) {
  return (
    <div
      role="status"
      className={cn("surface flex items-center gap-3 rounded-3xl p-6 text-sm text-ink-soft", className)}
    >
      <LoaderCircle className="size-4 shrink-0 motion-safe:animate-spin" aria-hidden="true" />
      {label}
    </div>
  );
}

/**
 * Empty and all-done states are yellow moments: flat sunflower, ink, a drawn illustration
 * (first on phones, as in the reference; beside the text on wider screens). Never glass.
 */
export function EmptyState({
  illustration,
  title,
  children,
  actions,
  className,
}: {
  illustration: ReactNode;
  title: string;
  children?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("moment grid items-center gap-5 rounded-3xl p-6 sm:grid-cols-[minmax(0,1fr)_13rem] sm:gap-8 sm:p-8", className)}>
      <div className="min-w-0">
        <h2 className="text-xl font-semibold tracking-[-0.02em]">{title}</h2>
        {children && <div className="mt-2 max-w-xl text-sm leading-relaxed text-sunflower-ink">{children}</div>}
        {actions && <div className="mt-5 flex flex-wrap gap-2">{actions}</div>}
      </div>
      <div className="mx-auto w-full max-w-52 max-sm:order-first sm:max-w-none">{illustration}</div>
    </div>
  );
}

/** Small "updating" label for a panel whose last result stays visible while refreshing. */
export function RefreshingLabel({ active, children }: { active: boolean; children: ReactNode }) {
  if (!active) return null;
  return (
    <p role="status" className="flex items-center gap-2 text-xs font-medium text-ink-soft">
      <LoaderCircle className="size-3.5 motion-safe:animate-spin" aria-hidden="true" />
      {children}
    </p>
  );
}
