"use client";

import Link from "next/link";
import { createContext, useContext, type ReactNode } from "react";
import { useWhatsAppEntry } from "@/hooks/use-whatsapp-entry";
import { DASHBOARD, WEB_START, type WhatsAppEntry } from "@/lib/whatsapp-entry";

const EntryContext = createContext<WhatsAppEntry>({ kind: "loading" });

/** One shared session check for the public page's actions and chat QR. */
export function WhatsAppEntryProvider({ children }: { children: ReactNode }) {
  const entry = useWhatsAppEntry();
  return <EntryContext value={entry}>{children}</EntryContext>;
}

export function useEntry(): WhatsAppEntry {
  return useContext(EntryContext);
}

const labels = {
  chat: "Start on WhatsApp",
  dashboard: "Open dashboard",
  loading: "Open FinBoy",
  web: "Get started",
};

/**
 * The page's main action. While the session loads, the dashboard's guard still routes an
 * early tap to the right place. `short` keeps the WhatsApp label compact on phones.
 */
export function StartLink({
  className,
  before,
  after,
  short = false,
}: {
  className?: string;
  before?: ReactNode;
  after?: ReactNode;
  short?: boolean;
}) {
  const entry = useEntry();
  const label = labels[entry.kind];
  const text = short && entry.kind === "chat" ? (
    <>
      <span className="sm:hidden">WhatsApp</span>
      <span className="max-sm:hidden">{label}</span>
    </>
  ) : (
    label
  );
  const content = (
    <>
      {before}
      {text}
      {after}
    </>
  );
  if (entry.kind === "chat") {
    return (
      <a
        href={entry.href}
        target="_blank"
        rel="noopener noreferrer"
        aria-label={short ? label : undefined}
        className={className}
      >
        {content}
      </a>
    );
  }
  return (
    <Link href={entry.kind === "web" ? WEB_START : DASHBOARD} className={className}>
      {content}
    </Link>
  );
}
