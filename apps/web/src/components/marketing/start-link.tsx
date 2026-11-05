"use client";

import Link from "next/link";
import { createContext, useContext, type ReactNode } from "react";
import { useWhatsAppEntry } from "@/hooks/use-whatsapp-entry";
import { WEB_START, type WhatsAppEntry } from "@/lib/whatsapp-entry";

const EntryContext = createContext<WhatsAppEntry>({ kind: "loading" });

/** One session request per page, shared by every Start button and the chat QR on it. */
export function WhatsAppEntryProvider({ children }: { children: ReactNode }) {
  const entry = useWhatsAppEntry();
  return <EntryContext value={entry}>{children}</EntryContext>;
}

export function useEntry(): WhatsAppEntry {
  return useContext(EntryContext);
}

const CHAT_LABEL = "Start on WhatsApp";
const WEB_LABEL = "Get started";

/**
 * The page's main action. While sign-ups are open it opens FinBoy's WhatsApp chat with
 * "Hi FinBoy" typed in; until the API answers it points at the sign-in page, so an early tap
 * still lands somewhere useful. `short` shows only "Start" on phones; the accessible name stays
 * whole and still contains the visible word.
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
  const label = entry.kind === "chat" ? CHAT_LABEL : WEB_LABEL;
  const text = short ? (
    <>
      <span className="sm:hidden">Start</span>
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
    <Link href={WEB_START} aria-label={short ? label : undefined} className={className}>
      {content}
    </Link>
  );
}
