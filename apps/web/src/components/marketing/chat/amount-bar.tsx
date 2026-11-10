"use client";

import { Camera, FaceSlightlySmiling, Mic, Paperclip, SendHorizontal } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";

/**
 * WhatsApp's message bar as a real field, only while FinBoy waits for the amount (after
 * ✏️ Amount). It takes digits, a comma, a point and ₹, so number words never reach the script. It
 * focuses without moving the page, and keeps a ≥3:1 outline as any enabled field must. The mic
 * becomes WhatsApp's send arrow once something is typed.
 */
export function AmountBar({ onSend }: { onSend: (text: string) => boolean }) {
  const id = useId();
  const field = useRef<HTMLInputElement>(null);
  const [value, setValue] = useState("");
  const ready = value.trim().length > 0;

  useEffect(() => {
    field.current?.focus({ preventScroll: true });
  }, []);

  return (
    <form
      className="flex shrink-0 items-center gap-1.5 px-1.5 pt-1 pb-2"
      onSubmit={(event) => {
        event.preventDefault();
        // Kept while FinBoy is still typing, so nothing typed is lost.
        if (ready && onSend(value)) setValue("");
      }}
    >
      <label htmlFor={id} className="sr-only">
        Message FinBoy the right amount
      </label>
      <div className="relative min-w-0 flex-1 text-wa-icon">
        <FaceSlightlySmiling className="pointer-events-none absolute top-1/2 left-3 size-6 -translate-y-1/2" aria-hidden="true" />
        <input
          id={id}
          ref={field}
          value={value}
          onChange={(event) => setValue(event.target.value.replace(/[^\d.,₹]/g, ""))}
          inputMode="decimal"
          enterKeyHint="send"
          autoComplete="off"
          maxLength={14}
          placeholder="Message"
          className="h-12 w-full rounded-full border border-wa-field-edge bg-wa-bar pr-20 pl-12 text-[17px] text-wa-text outline-none placeholder:text-wa-meta focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-wa-button"
        />
        <span className="pointer-events-none absolute top-1/2 right-3.5 flex -translate-y-1/2 items-center gap-3" aria-hidden="true">
          <Paperclip className="size-[1.375rem] -rotate-45" />
          <Camera className="size-[1.375rem]" />
        </span>
      </div>
      <button
        type="submit"
        aria-label="Send"
        disabled={!ready}
        className="grid size-12 shrink-0 place-items-center rounded-full bg-wa-accent text-white outline-none focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-wa-button"
      >
        {ready ? <SendHorizontal className="size-5" aria-hidden="true" /> : <Mic className="size-6" aria-hidden="true" />}
      </button>
    </form>
  );
}
