"use client";

import { X } from "lucide-react";
import { useEffect, useId, useRef, type KeyboardEvent } from "react";

import type { Listing } from "@/lib/chat-demo/script";

/**
 * WhatsApp's list sheet over the dimmed chat: the list's title with a round close, the section
 * title, one row per choice and "Tap an item to select it". Choosing a row sends it. Focus starts on
 * the first row and stays in the sheet; Escape closes it.
 */
export function ListSheet({
  listing,
  onPick,
  onClose,
}: {
  listing: Listing;
  onPick: (index: number) => void;
  onClose: () => void;
}) {
  const title = useId();
  const sheet = useRef<HTMLDivElement>(null);
  const first = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    first.current?.focus({ preventScroll: true });
  }, []);

  const keys = (event: KeyboardEvent) => {
    if (event.key === "Escape") {
      event.stopPropagation();
      onClose();
      return;
    }
    if (event.key !== "Tab" || !sheet.current) return;
    const buttons = [...sheet.current.querySelectorAll<HTMLButtonElement>("button")];
    const [start, end] = [buttons[0], buttons.at(-1)];
    if (event.shiftKey && document.activeElement === start) {
      event.preventDefault();
      end?.focus();
    } else if (!event.shiftKey && document.activeElement === end) {
      event.preventDefault();
      start?.focus();
    }
  };

  return (
    <div className="absolute inset-0 z-20 flex flex-col justify-end bg-black/40" onClick={onClose}>
      <div
        ref={sheet}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title}
        onClick={(event) => event.stopPropagation()}
        onKeyDown={keys}
        className="max-h-[78%] overflow-y-auto rounded-t-[1.25rem] bg-wa-in pb-2 text-wa-text"
      >
        <div className="sticky top-0 flex h-14 items-center justify-center bg-wa-in px-14">
          <h3 id={title} className="truncate text-[17px] font-medium">
            {listing.open}
          </h3>
          <button
            type="button"
            aria-label="Close"
            onClick={onClose}
            className="absolute right-3 grid size-8 place-items-center rounded-full bg-black/[0.06] text-wa-meta outline-none focus-visible:outline-2 focus-visible:outline-wa-button"
          >
            <X className="size-4" aria-hidden="true" />
          </button>
        </div>
        <p className="px-5 pt-1 pb-2 text-[13px] font-medium text-wa-meta">{listing.section}</p>
        <ul>
          {listing.rows.map((row, index) => (
            <li key={row.title} className="border-t border-black/10">
              <button
                ref={index === 0 ? first : undefined}
                type="button"
                onClick={() => onPick(index)}
                className="block w-full px-5 py-3.5 text-left text-base outline-none hover:bg-black/[0.03] focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-wa-button"
              >
                {row.title}
              </button>
            </li>
          ))}
        </ul>
        <p className="border-t border-black/10 pt-3 pb-1 text-center text-[12.5px] text-wa-meta">Tap an item to select it</p>
      </div>
    </div>
  );
}
