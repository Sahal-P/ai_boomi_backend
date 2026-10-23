"use client";

import { Activity, ArrowUpRight, Check, RefreshCw, Unplug } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useHealth } from "@/hooks/use-health";
import { cn } from "@/lib/utils";

const labels = {
  checking: "Checking connection",
  connected: "Connected to FinBoy",
  degraded: "Database unavailable",
  offline: "Backend is offline",
} as const;

export function ConnectionStatus() {
  const { connection, refresh } = useHealth();
  const isConnected = connection.state === "connected";
  const isChecking = connection.state === "checking";
  const apiConnected = isConnected || connection.state === "degraded";

  return (
    <section
      id="foundation"
      aria-labelledby="foundation-title"
      className="scroll-mt-8 rounded-2xl border bg-card p-6 sm:p-8"
    >
      <div className="flex flex-col justify-between gap-8 md:flex-row md:items-center">
        <div className="flex items-start gap-4">
          <span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-secondary text-primary">
            <Activity className="size-5" aria-hidden="true" />
          </span>
          <div>
            <p className="eyebrow mb-2">THE FOUNDATION</p>
            <h2
              id="foundation-title"
              className="text-xl font-medium tracking-tight"
            >
              A good place to begin.
            </h2>
            <p className="mt-2 max-w-sm text-sm leading-relaxed text-muted-foreground">
              FinBoy is taking shape. This is the first step
              <br className="hidden sm:block" /> toward a clearer money story.
            </p>
          </div>
        </div>
        <div className="min-w-0 md:w-[22rem]">
          <div className="flex items-center justify-between gap-3">
            <div
              role="status"
              aria-live="polite"
              aria-atomic="true"
              className="flex items-center gap-2.5 text-sm font-medium"
            >
              <span
                className={cn(
                  "size-2 shrink-0 rounded-full",
                  isConnected
                    ? "bg-primary"
                    : isChecking
                      ? "bg-muted-foreground motion-safe:animate-pulse"
                      : "bg-amber-600",
                )}
                aria-hidden="true"
              />
              {labels[connection.state]}
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => void refresh()}
              disabled={isChecking}
              aria-label="Refresh connection status"
              className="size-11 shrink-0 text-muted-foreground"
            >
              <RefreshCw
                className={cn(
                  "size-4",
                  isChecking && "motion-safe:animate-spin",
                )}
                aria-hidden="true"
              />
            </Button>
          </div>
          <div className="mt-3 flex flex-wrap gap-x-5 gap-y-2 border-t pt-3 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5">
              {apiConnected ? (
                <Check className="size-3.5 text-primary" aria-hidden="true" />
              ) : (
                <Unplug className="size-3.5" aria-hidden="true" />
              )}
              API{" "}
              {isChecking
                ? "checking"
                : apiConnected
                  ? "connected"
                  : "unreachable"}
            </span>
            <span className="flex items-center gap-1.5">
              {isConnected ? (
                <Check className="size-3.5 text-primary" aria-hidden="true" />
              ) : (
                <Unplug className="size-3.5" aria-hidden="true" />
              )}
              PostgreSQL{" "}
              {isChecking
                ? "checking"
                : isConnected
                  ? "connected"
                  : connection.state === "degraded"
                    ? "unavailable"
                    : "unknown"}
            </span>
          </div>
          <p className="mt-3 text-[11px] text-muted-foreground">
            {connection.state === "checking"
              ? "Checking the live backend…"
              : `Checked ${connection.checkedAt.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit", second: "2-digit", timeZone: "Asia/Kolkata" })} IST · Refreshes every 30s`}
          </p>
        </div>
      </div>
      <noscript>
        <p className="mt-4 text-sm text-muted-foreground">
          Enable JavaScript to check the live connection.
        </p>
      </noscript>
      <div className="mt-6 flex items-center gap-1.5 border-t pt-4 text-xs text-muted-foreground">
        <ArrowUpRight className="size-3.5" aria-hidden="true" />
        An early preview. Personal finance features are coming later.
      </div>
    </section>
  );
}
