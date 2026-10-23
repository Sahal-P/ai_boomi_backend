import type { ReactNode } from "react";

import { Reveal } from "@/components/motion/reveal";
import { cn } from "@/lib/utils";

type SectionHeadingProps = {
  eyebrow: string;
  title: ReactNode;
  description?: ReactNode;
  align?: "left" | "center";
  className?: string;
  id?: string;
};

export function SectionHeading({ eyebrow, title, description, align = "left", className, id }: SectionHeadingProps) {
  return (
    <Reveal className={cn(align === "center" && "mx-auto text-center", "max-w-3xl", className)}>
      <p className="eyebrow text-violet">{eyebrow}</p>
      <h2
        id={id}
        className="mt-4 text-[clamp(2.1rem,4.2vw,3.6rem)] leading-[1.05] font-semibold tracking-[-0.04em] text-balance text-ink"
      >
        {title}
      </h2>
      {description ? (
        <p className={cn("mt-5 max-w-xl text-[1.0625rem] leading-relaxed text-ink-soft", align === "center" && "mx-auto")}>
          {description}
        </p>
      ) : null}
    </Reveal>
  );
}
