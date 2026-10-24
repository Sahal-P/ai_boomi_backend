import { LoaderCircle } from "lucide-react";
import type { ComponentType, ReactNode } from "react";
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

export function EmptyState({
  icon: Icon,
  title,
  children,
  actions,
  className,
}: {
  icon: ComponentType<{ className?: string; "aria-hidden"?: boolean | "true" }>;
  title: string;
  children?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("surface rounded-3xl p-6 sm:p-8", className)}>
      <Icon className="size-7 text-violet-deep" aria-hidden="true" />
      <h2 className="mt-4 text-lg font-semibold">{title}</h2>
      {children && <div className="mt-2 max-w-xl text-sm leading-relaxed text-ink-soft">{children}</div>}
      {actions && <div className="mt-5 flex flex-wrap gap-2">{actions}</div>}
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
