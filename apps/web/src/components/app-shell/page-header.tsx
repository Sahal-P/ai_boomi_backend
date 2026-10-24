import type { ReactNode } from "react";

/** The one app page header: a direct task title, short supporting text, actions on the right. */
export function PageHeader({
  title,
  description,
  actions,
  children,
}: {
  title: string;
  description?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-4">
      <div className="min-w-0 max-w-2xl">
        <h1 className="text-[1.75rem] leading-tight font-semibold tracking-[-0.03em] sm:text-[2rem]">
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
