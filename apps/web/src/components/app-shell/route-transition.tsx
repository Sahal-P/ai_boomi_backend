"use client";

import { usePathname } from "next/navigation";
import { ViewTransition, type ReactNode } from "react";

/**
 * Pages fade in when the route changes. A search-param change (opening a record, a filter, a
 * Reports period) updates the same page and doesn't animate: a page transition paints above
 * everything, so it would draw the old page over an open dialog.
 */
export function RouteTransition({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <ViewTransition key={pathname} enter="page" exit="page" default="none">
      {children}
    </ViewTransition>
  );
}
