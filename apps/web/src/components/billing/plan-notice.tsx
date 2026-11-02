"use client";

import { ChevronRight, CircleAlert, Sparkles } from "lucide-react";
import { useHouseholdAccess } from "@/components/app-shell/household-context";
import { usePremium } from "@/components/billing/premium-provider";
import { Button } from "@/components/ui/button";
import { homeNotice } from "@/lib/plan";

/** Home's one line about the plan: quiet until the last week of Premium, amber if a renewal failed. */
export function PlanNotice() {
  const { plan } = useHouseholdAccess();
  const premium = usePremium();
  const notice = homeNotice(plan);
  if (!notice) return null;
  if (notice.tone === "attention") {
    return (
      <button
        type="button"
        onClick={() => premium.open()}
        className="inline-flex min-h-11 items-center gap-2 rounded-full border border-amber-200 bg-amber-50 py-2 pr-3 pl-4 text-sm font-medium text-amber-950 transition-colors hover:bg-amber-100/70"
      >
        <CircleAlert className="size-4 shrink-0 text-amber-800" aria-hidden="true" />
        {notice.text} · {notice.action}
        <ChevronRight className="size-4 shrink-0 text-amber-800" aria-hidden="true" />
      </button>
    );
  }
  return (
    <div className="surface flex flex-wrap items-center gap-x-4 gap-y-3 rounded-2xl px-4 py-3">
      <Sparkles className="size-4 shrink-0" aria-hidden="true" />
      <p className="min-w-0 flex-1 text-sm font-medium">{notice.text}</p>
      <Button size="sm" onClick={() => premium.open()}>
        {notice.action}
      </Button>
    </div>
  );
}
