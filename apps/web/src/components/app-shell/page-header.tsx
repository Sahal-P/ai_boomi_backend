import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

/**
 * The one app page header: a direct task title, short supporting text, actions on the right.
 * Screens reached from another one (an import from Sources) get the reference's glass back
 * button; top-level tabs never do.
 */
export function PageHeader({
  title,
  description,
  actions,
  back,
  children,
}: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  back?: { href: string; label: string };
  children?: ReactNode;
}) {
  return (
    <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-4">
      <div className="min-w-0 max-w-2xl">
        {back && (
          <Link
            href={back.href}
            aria-label={back.label}
            data-glass-press=""
            className="lg-static mb-4 grid size-11 place-items-center rounded-full text-ink hover:[--lg-static-tint:0.8]"
          >
            <ArrowLeft className="size-5" aria-hidden="true" />
          </Link>
        )}
        <h1 className="text-[1.75rem] leading-tight font-medium tracking-[-0.025em] sm:text-[2rem]">
          {title}
        </h1>
        {description && (
          <p className="mt-1.5 text-sm leading-relaxed text-ink-soft">{description}</p>
        )}
        {children}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2 max-sm:w-full">{actions}</div>}
    </header>
  );
}
