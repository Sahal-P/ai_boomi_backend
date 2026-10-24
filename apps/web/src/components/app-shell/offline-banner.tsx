"use client";

import { WifiOff } from "lucide-react";
import { useOnline } from "@/hooks/use-online";

/** Device-level connectivity. Panels keep their last loaded view and label it themselves. */
export function OfflineBanner() {
  const online = useOnline();
  return (
    <div role="status" aria-live="polite">
      {!online && (
        <p className="mb-5 flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm leading-relaxed text-amber-950">
          <WifiOff className="mt-0.5 size-4 shrink-0 text-amber-800" aria-hidden="true" />
          <span>
            <strong className="font-semibold">You&apos;re offline.</strong> You&apos;re seeing what
            was last loaded. Changes can&apos;t be saved until you reconnect; FinBoy will refresh
            automatically.
          </span>
        </p>
      )}
    </div>
  );
}
