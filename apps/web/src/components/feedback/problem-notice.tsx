import { TriangleAlert, WifiOff } from "lucide-react";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import type { Problem } from "@/lib/messages";
import { cn } from "@/lib/utils";

/** A task failure: what didn't happen, whether data changed, and the next action. */
export function ProblemNotice({
  problem,
  onRetry,
  retryLabel = "Try again",
  id,
  className,
  children,
  live = true,
}: {
  problem: Problem;
  onRetry?: (() => void) | undefined;
  retryLabel?: string;
  id?: string;
  className?: string;
  children?: ReactNode;
  /** Announce immediately (alert). Use false for failures already announced elsewhere. */
  live?: boolean;
}) {
  const Icon = problem.kind === "offline" ? WifiOff : TriangleAlert;
  return (
    <div
      id={id}
      role={live ? "alert" : undefined}
      className={cn(
        "flex gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-relaxed text-amber-950",
        className,
      )}
    >
      <Icon className="mt-0.5 size-4 shrink-0 text-amber-800" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="font-semibold">{problem.title}</p>
        <p className="mt-0.5">{problem.detail}</p>
        {children}
        {(onRetry || problem.reference) && (
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2">
            {onRetry && (
              <Button size="sm" variant="outline" onClick={onRetry}>
                {retryLabel}
              </Button>
            )}
            {problem.reference && (
              <p className="text-xs break-all text-amber-900">
                Reference: <span className="font-mono select-all">{problem.reference}</span>
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
