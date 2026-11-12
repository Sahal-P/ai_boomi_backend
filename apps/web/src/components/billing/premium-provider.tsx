"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useHouseholdAccess } from "@/components/app-shell/household-context";
import { PremiumSheet } from "@/components/billing/premium-sheet";
import type { Feature } from "@/lib/plan";
import { onPremiumRequired } from "@/lib/premium-events";

type PremiumValue = {
  /** True on Premium, on an included household, and whenever billing is off. */
  premium: boolean;
  open: (feature?: Feature) => void;
  /** Runs `action` on Premium; otherwise opens the upgrade sheet about that feature. */
  guard: (feature: Feature, action: () => void) => void;
};

const PremiumContext = createContext<PremiumValue | null>(null);

/** One upgrade sheet for the whole app, mounted beside quick add. Any `premium_required` answer
 *  from the API opens it too, wherever the person was. */
export function PremiumProvider({ children }: { children: ReactNode }) {
  const { plan, advisor } = useHouseholdAccess();
  const [open, setOpen] = useState(false);
  const [feature, setFeature] = useState<Feature | null>(null);
  const premium = plan === null || plan.premium;

  const show = useCallback(
    (next?: Feature) => {
      if (!plan) return;
      setFeature(next ?? null);
      setOpen(true);
    },
    [plan],
  );
  useEffect(() => onPremiumRequired(() => show()), [show]);

  const value = useMemo<PremiumValue>(
    () => ({
      premium,
      open: show,
      guard: (wanted, action) => (premium ? action() : show(wanted)),
    }),
    [premium, show],
  );

  return (
    <PremiumContext value={value}>
      {children}
      {plan && <PremiumSheet open={open} onOpenChange={setOpen} plan={plan} feature={feature} advisor={advisor} />}
    </PremiumContext>
  );
}

export function usePremium() {
  const context = useContext(PremiumContext);
  if (!context) throw new Error("usePremium must be used inside PremiumProvider");
  return context;
}
