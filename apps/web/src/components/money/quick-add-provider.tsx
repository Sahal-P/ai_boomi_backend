"use client";

import { createContext, useContext, useMemo, useState, type ReactNode } from "react";
import { QuickAdd } from "@/components/money/quick-add";
import { emitRecordsChanged } from "@/lib/record-events";

const QuickAddContext = createContext<{ open: () => void } | null>(null);

/** One quick-add sheet for the whole app: the + on every screen opens it, and a save or an undo
 *  tells every screen holding totals or lists to reload. */
export function QuickAddProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const value = useMemo(() => ({ open: () => setOpen(true) }), []);
  return (
    <QuickAddContext value={value}>
      {children}
      <QuickAdd open={open} onOpenChange={setOpen} onSaved={emitRecordsChanged} />
    </QuickAddContext>
  );
}

export function useQuickAdd() {
  const context = useContext(QuickAddContext);
  if (!context) throw new Error("useQuickAdd must be used inside QuickAddProvider");
  return context;
}
