import Image from "next/image";
import Link from "next/link";

import { cn } from "@/lib/utils";

/** The approved companion mark: a lowercase b with a conversation bubble in its counter. */
export function BrandMark({ className }: { className?: string }) {
  return (
    <Image
      src="/brand/finboy-mark.svg"
      alt=""
      aria-hidden="true"
      width={128}
      height={128}
      unoptimized
      className={cn("size-8 shrink-0", className)}
    />
  );
}

export function Brand({ href = "/", className }: { href?: string; className?: string }) {
  return (
    <Link href={href} aria-label="FinBoy home" className={cn("inline-flex shrink-0 items-center", className)}>
      <Image
        src="/brand/finboy-logo.svg"
        alt=""
        aria-hidden="true"
        width={485}
        height={128}
        unoptimized
        className="h-8 w-auto"
      />
    </Link>
  );
}
