"use client";

import { MessageCircle } from "lucide-react";
import { type CSSProperties, useEffect, useState } from "react";
import { chatLink, getSession } from "@/lib/api/auth";

/** One tap from the landing page into FinBoy's WhatsApp chat, shown only while sign-ups are open. */
export function WhatsAppStart({ className, style }: { className?: string; style?: CSSProperties }) {
  const [number, setNumber] = useState<string | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    getSession(controller.signal).then(
      ({ sign_in }) => {
        if (sign_in.whatsapp && sign_in.signup_open && sign_in.whatsapp_number) {
          setNumber(sign_in.whatsapp_number);
        }
      },
      // Without it the page still works: Get started free leads to every way in.
      () => undefined,
    );
    return () => controller.abort();
  }, []);
  if (!number) return null;
  return (
    <p className={className} style={style}>
      <MessageCircle className="mr-1.5 inline size-4 align-[-3px] text-ink" aria-hidden="true" />
      Prefer WhatsApp?{" "}
      <a
        href={chatLink(number)}
        target="_blank"
        rel="noopener noreferrer"
        className="font-semibold text-ink underline underline-offset-4"
      >
        Say hi to FinBoy
      </a>{" "}
      and keep track by voice — no password.
    </p>
  );
}
