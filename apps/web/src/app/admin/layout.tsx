import type { Metadata } from "next";
import type { ReactNode } from "react";

// The admin panel (docs/admin-round/contract.md): never indexed, framed or cached
// (next.config.ts sends the headers). The API enforces every rule; these pages only steer.
export const metadata: Metadata = {
  title: { default: "FinBoy admin", template: "%s · FinBoy admin" },
  robots: { index: false, follow: false, nocache: true },
  referrer: "no-referrer",
};

export default function AdminLayout({ children }: { children: ReactNode }) {
  return children;
}
