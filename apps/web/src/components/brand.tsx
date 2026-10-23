import { Asterisk } from "lucide-react";

export function Brand() {
  return (
    <a
      href="#"
      aria-label="FinBoy home"
      className="inline-flex items-center gap-2.5"
    >
      <span className="flex size-9 items-center justify-center rounded-xl bg-foreground text-background">
        <Asterisk className="size-6" strokeWidth={2.3} aria-hidden="true" />
      </span>
      <span className="text-[1.6rem] font-semibold tracking-[-0.065em]">
        finboy<span className="text-primary">.</span>
      </span>
    </a>
  );
}
