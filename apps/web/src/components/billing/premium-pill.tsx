import { cn } from "@/lib/utils";

/** Marks a control that needs Premium on the Free plan: ink on sunflower, a fill under ink only. */
export function PremiumPill({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex h-5 items-center rounded-full bg-sunflower px-2 text-[11px] leading-none font-semibold tracking-wide text-ink",
        className,
      )}
    >
      Premium
    </span>
  );
}
