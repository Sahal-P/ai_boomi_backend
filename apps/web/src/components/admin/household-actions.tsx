"use client";

import { Check, Copy } from "lucide-react";
import { useId, useState, type ReactNode } from "react";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAction } from "@/hooks/use-action";
import { actionLabels } from "@/lib/admin-labels";
import {
  actOnHousehold,
  createPayLink,
  eraseHousehold,
  grantPremium,
  type HouseholdAction,
  type HouseholdDetail,
  type SimpleAction,
} from "@/lib/api/admin";

// The order buttons appear in; the API decides which are allowed for this household.
const ORDER: HouseholdAction[] = ["sign_out", "suspend", "restore", "premium", "pay_link", "autopay_cancel", "erase"];
const PATHS: Partial<Record<HouseholdAction, SimpleAction>> = {
  sign_out: "sign-out",
  suspend: "suspend",
  restore: "restore",
  autopay_cancel: "autopay/cancel",
};

type Copy = {
  title: string;
  body: (detail: HouseholdDetail) => ReactNode;
  confirm: string;
  busy: string;
  done: string;
  failure: string;
  /** Typing the short ID back is required. */
  typed?: boolean;
  destructive?: boolean;
};

const ERASE_BODY: Record<HouseholdDetail["kind"], string> = {
  self_serve:
    "This deletes the household's records, sign-in and plan, turns AutoPay off at the bank and revokes Gmail, exactly as “Delete my account” does. FinBoy's own payment records stay.",
  pilot: "This erases the household's records and WhatsApp state, as the pilot eraser does. Its row stays as a former pilot.",
  pending: "This sign-up never agreed, so nothing of it is kept.",
  owner: "",
  former_pilot: "",
};

const COPY: Record<HouseholdAction, Copy> = {
  sign_out: {
    title: "Sign this household out everywhere?",
    body: (detail) => `Every browser signed in to ${detail.short_id} is signed out now. Nothing in their records changes.`,
    confirm: "Sign out everywhere",
    busy: "Signing out…",
    done: "Signed out everywhere.",
    failure: "The household wasn't signed out",
  },
  suspend: {
    title: "Suspend this household?",
    body: (detail) =>
      `Until you restore it, ${detail.short_id} can't sign in and gets no WhatsApp replies, reminders or charges. Their web sessions end now and AutoPay is turned off at the bank.`,
    confirm: "Suspend",
    busy: "Suspending…",
    done: "Household suspended.",
    failure: "The household wasn't suspended",
    typed: true,
    destructive: true,
  },
  restore: {
    title: "Restore this household?",
    body: (detail) =>
      `${detail.short_id} can sign in again. If they sent STOP on WhatsApp, replies stay off until they send START.`,
    confirm: "Restore",
    busy: "Restoring…",
    done: "Household restored.",
    failure: "The household wasn't restored",
  },
  premium: {
    title: "Give Premium days",
    body: () => "Days are added after their current paid time, or from today. Nothing is charged.",
    confirm: "Give days",
    busy: "Giving days…",
    done: "Premium days given.",
    failure: "Premium days weren't given",
  },
  pay_link: {
    title: "Create a pay link?",
    body: (detail) =>
      `The link pays ₹299 for ${detail.short_id} and works for 7 days. Anyone holding it can pay, so send it only to the household, privately. It's shown once.`,
    confirm: "Create link",
    busy: "Creating…",
    done: "Pay link created.",
    failure: "The pay link wasn't created",
  },
  autopay_cancel: {
    title: "Turn off AutoPay?",
    body: () => "The mandate is revoked at the bank, so nothing more is taken. Premium lasts to the end of the paid month.",
    confirm: "Turn off AutoPay",
    busy: "Turning off…",
    done: "AutoPay turned off.",
    failure: "AutoPay wasn't turned off",
    destructive: true,
  },
  erase: {
    title: "Erase this household?",
    body: (detail) => `${ERASE_BODY[detail.kind]} This can't be undone.`,
    confirm: "Erase",
    busy: "Erasing…",
    done: "Household erased.",
    failure: "The household wasn't erased",
    typed: true,
    destructive: true,
  },
};

/** What an admin may do to one household, each behind a confirmation that waits for the server. */
export function HouseholdActions({
  detail,
  onUpdated,
  onErased,
  announce,
}: {
  detail: HouseholdDetail;
  onUpdated: (next: HouseholdDetail) => void;
  onErased: () => void;
  announce: (message: string) => void;
}) {
  const ids = useId();
  const [open, setOpen] = useState<HouseholdAction | null>(null);
  const [typed, setTyped] = useState("");
  const [days, setDays] = useState("30");
  const [link, setLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const action = useAction();
  const allowed = ORDER.filter((name) => detail.actions.includes(name));
  const copy = open ? COPY[open] : null;
  const dayCount = Number(days);
  const daysValid = /^\d{1,3}$/.test(days) && dayCount >= 1 && dayCount <= 366;
  const ready =
    open !== null &&
    (!COPY[open].typed || typed.trim().toLowerCase() === detail.short_id) &&
    (open !== "premium" || daysValid);
  // An erase waits for a running import; the generic "try again" copy would misdescribe it.
  const problem =
    action.problem && open === "erase" && action.problem.code === "try_later"
      ? { ...action.problem, detail: "An import is running for this household. Nothing was erased. Try again in a minute." }
      : action.problem;

  function start(name: HouseholdAction) {
    action.clear();
    setTyped("");
    setDays("30");
    setLink(null);
    setCopied(false);
    setOpen(name);
  }

  async function confirm() {
    if (!open || !ready) return;
    const name = open;
    const done = await action.run(name, COPY[name].failure, async () => {
      if (name === "pay_link") {
        setLink((await createPayLink(detail.id)).url);
      } else if (name === "erase") {
        await eraseHousehold(detail.id, typed.trim().toLowerCase());
        onErased();
      } else if (name === "premium") {
        onUpdated(await grantPremium(detail.id, dayCount));
      } else {
        const path = PATHS[name];
        if (path) onUpdated(await actOnHousehold(detail.id, path));
      }
      return true;
    });
    if (!done) return;
    announce(COPY[name].done);
    if (name !== "pay_link") setOpen(null);
  }

  async function copyLink() {
    if (!link) return;
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  if (!allowed.length) {
    return (
      <p className="text-sm text-ink-soft">
        {detail.kind === "owner"
          ? "The owner's household can only be viewed here."
          : "Nothing can be changed for this household."}
      </p>
    );
  }

  return (
    <>
      <div className="flex flex-wrap gap-2">
        {allowed.map((name) => (
          <Button
            key={name}
            size="sm"
            variant={name === "erase" ? "destructive" : "outline"}
            onClick={() => start(name)}
          >
            {actionLabels[name]}
          </Button>
        ))}
      </div>
      <AlertDialog open={open !== null} onOpenChange={(next) => !next && !action.busy && setOpen(null)}>
        <AlertDialogContent>
          {copy && open && (
            <form
              onSubmit={(event) => {
                event.preventDefault();
                void confirm();
              }}
            >
              <AlertDialogHeader>
                <AlertDialogTitle>{link ? "Pay link, shown once" : copy.title}</AlertDialogTitle>
                <AlertDialogDescription>
                  {link ? "Copy it now and send it to the household privately. It works for 7 days." : copy.body(detail)}
                </AlertDialogDescription>
              </AlertDialogHeader>
              <div className="mt-4 space-y-3">
                {open === "premium" && (
                  <div>
                    <label htmlFor={`${ids}-days`} className="text-sm font-semibold">
                      Days of Premium
                    </label>
                    <Input
                      id={`${ids}-days`}
                      type="number"
                      inputMode="numeric"
                      min={1}
                      max={366}
                      required
                      value={days}
                      aria-describedby={`${ids}-days-hint`}
                      onChange={(event) => setDays(event.target.value)}
                      className="mt-1.5 max-w-40"
                    />
                    <p id={`${ids}-days-hint`} className="mt-1 text-xs text-ink-soft">
                      From 1 to 366.
                    </p>
                  </div>
                )}
                {copy.typed && (
                  <div>
                    <label htmlFor={`${ids}-typed`} className="text-sm font-semibold">
                      Type <span className="font-mono">{detail.short_id}</span> to confirm
                    </label>
                    <Input
                      id={`${ids}-typed`}
                      autoComplete="off"
                      spellCheck={false}
                      maxLength={8}
                      value={typed}
                      onChange={(event) => setTyped(event.target.value)}
                      className="mt-1.5 max-w-48 font-mono"
                    />
                  </div>
                )}
                {link && (
                  <div>
                    <label htmlFor={`${ids}-link`} className="text-sm font-semibold">
                      Pay link
                    </label>
                    <div className="mt-1.5 flex gap-2">
                      <Input
                        id={`${ids}-link`}
                        readOnly
                        value={link}
                        onFocus={(event) => event.currentTarget.select()}
                        className="min-w-0 flex-1 font-mono text-xs"
                      />
                      <Button type="button" variant="outline" onClick={() => void copyLink()}>
                        {copied ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
                        {copied ? "Copied" : "Copy"}
                      </Button>
                    </div>
                  </div>
                )}
                {problem && <ProblemNotice problem={problem} />}
              </div>
              <AlertDialogFooter className="mt-5">
                {link ? (
                  <AlertDialogAction type="button" onClick={() => setOpen(null)}>
                    Done
                  </AlertDialogAction>
                ) : (
                  <>
                    <AlertDialogCancel type="button" disabled={action.busy !== null}>
                      Cancel
                    </AlertDialogCancel>
                    <Button type="submit" variant={copy.destructive ? "destructive" : "default"} disabled={!ready || action.busy !== null}>
                      {action.busy ? copy.busy : copy.confirm}
                    </Button>
                  </>
                )}
              </AlertDialogFooter>
            </form>
          )}
        </AlertDialogContent>
      </AlertDialog>
    </>
  );
}
