"use client";

import { QrCode } from "lucide-react";

import { LinkCode } from "@/components/app-shell/link-code";
import { useEntry } from "@/components/marketing/start-link";
import { useMediaQuery } from "@/hooks/use-media-query";

/** On a computer, a code that opens FinBoy's chat on the phone — only while sign-ups are open. */
export function ChatCode() {
  const entry = useEntry();
  const wide = useMediaQuery("(min-width: 64rem)");
  if (entry.kind !== "chat" || !wide) return null;
  return (
    <div className="surface flex items-center gap-5 rounded-[1.75rem] p-5">
      <LinkCode link={entry.href} size={160} />
      <div>
        <p className="flex items-center gap-2 font-semibold text-ink">
          <QrCode className="size-4" aria-hidden="true" /> On a computer?
        </p>
        <p className="mt-1.5 text-sm leading-relaxed text-ink-soft">
          Scan this with your phone’s camera. WhatsApp opens with “Hi FinBoy” typed in.
        </p>
      </div>
    </div>
  );
}
