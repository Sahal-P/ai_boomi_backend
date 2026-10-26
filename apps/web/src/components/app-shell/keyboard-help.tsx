"use client";

import { Keyboard, X } from "lucide-react";
import { Dialog } from "radix-ui";
import { useEffect, useSyncExternalStore } from "react";
import { Button } from "@/components/ui/button";
import {
  setShortcutsEnabled,
  shortcutsEnabled,
  subscribeShortcuts,
  typingTarget,
} from "@/lib/shortcuts";

const listeners = new Set<() => void>();
let open = false;

export function openKeyboardHelp() {
  open = true;
  listeners.forEach((listener) => listener());
}

function setOpen(value: boolean) {
  open = value;
  listeners.forEach((listener) => listener());
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

const rows = [
  { keys: ["?"], action: "Show these shortcuts" },
  { keys: ["/"], action: "Search records (Transactions and Review)" },
  { keys: ["j", "↓"], action: "Next record in Review" },
  { keys: ["k", "↑"], action: "Previous record in Review" },
  { keys: ["Esc"], action: "Close a record (asks first if you have unsaved changes)" },
];

/** Discoverable keyboard help. Single-key shortcuts can be turned off (WCAG 2.1.4). */
export function KeyboardHelp() {
  const isOpen = useSyncExternalStore(subscribe, () => open, () => false);
  const enabled = useSyncExternalStore(subscribeShortcuts, shortcutsEnabled, () => true);
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key !== "?" || event.metaKey || event.ctrlKey || event.altKey) return;
      if (!shortcutsEnabled() || typingTarget(event.target)) return;
      event.preventDefault();
      openKeyboardHelp();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  return (
    <Dialog.Root open={isOpen} onOpenChange={setOpen}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-ink/20 backdrop-blur-sm" />
        <Dialog.Content className="fixed top-1/2 left-1/2 z-50 max-h-[90dvh] w-[calc(100%-1.5rem)] max-w-md -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-3xl float-panel p-6">
          <Dialog.Title className="flex items-center gap-2 pr-10 text-lg font-semibold">
            <Keyboard className="size-5 text-ink" aria-hidden="true" /> Keyboard shortcuts
          </Dialog.Title>
          <Dialog.Description className="mt-1 text-sm text-ink-soft">
            Single-key shortcuts work when you aren&apos;t typing in a field.
          </Dialog.Description>
          <dl className="mt-5 divide-y text-sm">
            {rows.map((row) => (
              <div key={row.action} className="flex items-center justify-between gap-4 py-2.5">
                <dt className="text-ink-soft">{row.action}</dt>
                <dd className="flex shrink-0 gap-1">
                  {row.keys.map((key) => (
                    <kbd
                      key={key}
                      className="min-w-7 rounded-lg border bg-ink/[0.05] px-2 py-1 text-center font-mono text-xs font-semibold text-ink"
                    >
                      {key}
                    </kbd>
                  ))}
                </dd>
              </div>
            ))}
          </dl>
          <label className="mt-5 flex min-h-11 items-center gap-3 rounded-2xl bg-ink/[0.04] px-4 text-sm font-medium">
            <input
              type="checkbox"
              className="size-4 accent-[var(--violet)]"
              checked={enabled}
              onChange={(event) => setShortcutsEnabled(event.target.checked)}
            />
            Use single-key shortcuts
          </label>
          <Dialog.Close asChild>
            <Button
              variant="ghost"
              size="icon"
              aria-label="Close keyboard shortcuts"
              className="absolute top-3 right-3"
            >
              <X className="size-5" aria-hidden="true" />
            </Button>
          </Dialog.Close>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
