"use client";

import Link from "next/link";
import { createContext, useContext, useMemo, type ReactNode } from "react";
import { useVisit } from "@/hooks/use-visit";
import { useWhatsAppEntry } from "@/hooks/use-whatsapp-entry";
import { greeting, tapVisit, type PageLanguage } from "@/lib/api/visits";
import { DASHBOARD, WEB_START, type WhatsAppEntry } from "@/lib/whatsapp-entry";

type Entry = { entry: WhatsAppEntry; ref: string | null };
const EntryContext = createContext<Entry>({ entry: { kind: "loading" }, ref: null });

/**
 * One shared session check for the public page's actions and chat QR, and the page's visit
 * (docs/ad-journey-round/contract.md): its ref rides in the greeting the chat link types in.
 */
export function WhatsAppEntryProvider({
  children,
  language = "en",
  number = null,
}: {
  children: ReactNode;
  language?: PageLanguage;
  number?: string | null;
}) {
  const ref = useVisit(language);
  const entry = useWhatsAppEntry(greeting(language, ref), number);
  const value = useMemo(() => ({ entry, ref }), [entry, ref]);
  return <EntryContext value={value}>{children}</EntryContext>;
}

export function useEntry(): WhatsAppEntry {
  return useContext(EntryContext).entry;
}

type Labels = Record<WhatsAppEntry["kind"], string>;
const ENGLISH: Labels = {
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
  labels = ENGLISH,
}: {
  className?: string;
  before?: ReactNode;
  after?: ReactNode;
  short?: boolean;
  labels?: Labels;
}) {
  const { entry, ref } = useContext(EntryContext);
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
        onClick={() => tapVisit(ref)}
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
