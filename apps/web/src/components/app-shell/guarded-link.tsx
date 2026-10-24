"use client";

import Link from "next/link";
import type { ComponentProps } from "react";
import { hasUnsavedWork, requestLeave } from "@/lib/unsaved-work";

/** An in-app link that asks before discarding unsaved drafts (Back keeps drafts in memory). */
export function GuardedLink({
  href,
  onNavigate,
  ...props
}: Omit<ComponentProps<typeof Link>, "href"> & { href: string }) {
  return (
    <Link
      href={href}
      {...props}
      onNavigate={(event) => {
        onNavigate?.(event);
        if (hasUnsavedWork()) {
          event.preventDefault();
          requestLeave(href);
        }
      }}
    />
  );
}
