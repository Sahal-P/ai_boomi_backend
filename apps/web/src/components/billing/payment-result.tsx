"use client";

import { LoaderCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { getReceipt, type Receipt } from "@/lib/api/billing";
import { isAbort } from "@/lib/api/http";
import { shortDate } from "@/lib/plan";

const FIRST_DELAY = 1_500;
const LONGEST_DELAY = 5_000;
const GIVE_UP_AFTER = 60_000;

/** Polls one payment until PayU's answer is known: fast at first, then backing off. */
export function useReceipt(paymentId: string | null, onPaid?: () => void) {
  const [receipt, setReceipt] = useState<Receipt | null>(null);
  const [waitedLong, setWaitedLong] = useState(false);
  // The latest callback, so a parent re-rendering never restarts the polling below.
  const paid = useRef(onPaid);
  useEffect(() => {
    paid.current = onPaid;
  });
  useEffect(() => {
    if (!paymentId || paymentId === "unknown") return;
    const controller = new AbortController();
    const started = Date.now();
    let delay = FIRST_DELAY;
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function poll() {
      try {
        const next = await getReceipt(paymentId as string, controller.signal);
        if (controller.signal.aborted) return;
        setReceipt(next);
        if (next.status === "paid") {
          paid.current?.();
          return;
        }
        if (next.status === "failed" || next.status === "abandoned") return;
      } catch (error) {
        if (isAbort(error) || controller.signal.aborted) return;
      }
      if (Date.now() - started > GIVE_UP_AFTER) {
        setWaitedLong(true);
        return;
      }
      timer = setTimeout(poll, delay);
      delay = Math.min(delay * 1.5, LONGEST_DELAY);
    }
    void poll();
    return () => {
      controller.abort();
      if (timer) clearTimeout(timer);
    };
  }, [paymentId]);
  return { receipt, waitedLong };
}

/** A drawn check mark; it draws itself once, and simply appears under reduced motion. */
function DrawnCheck() {
  return (
    <svg viewBox="0 0 52 52" className="size-14" aria-hidden="true">
      <circle cx="26" cy="26" r="24" fill="none" stroke="currentColor" strokeWidth="3" pathLength={1} className="check-ring" />
      <path
        d="M15 27l7 7 15-16"
        fill="none"
        stroke="currentColor"
        strokeWidth="4"
        strokeLinecap="round"
        strokeLinejoin="round"
        pathLength={1}
        className="check-tick"
      />
    </svg>
  );
}

/**
 * What happened at PayU, shown the moment the person is back: a yellow moment when it is paid,
 * a calm wait while the bank confirms, and a plain way to try again when it did not go through.
 */
export function PaymentResult({
  paymentId,
  onPaid,
  onDone,
  onRetry,
  formatDate = shortDate,
  onPage = false,
  words = {
    paid: "You're on Premium",
    paidThrough: (date: string) => `Paid through ${date}.`,
    autopay: "AutoPay is on — it renews by itself.",
    done: "Done",
    checking: "Checking your payment…",
    confirming: "Confirming with your bank…",
    confirmingDetail: "This usually takes under a minute. You can leave this page — Premium switches on by itself.",
    slow: "Still confirming with your bank. Premium switches on as soon as it does; if money left your account and it doesn't, your bank returns it.",
    failed: "Payment didn't go through",
    failedDetail: "No charge was made. If money left your account, your bank returns it within 5–7 working days.",
    retry: "Try again",
  },
}: {
  paymentId: string;
  onPaid?: () => void;
  onDone: () => void;
  onRetry: () => void;
  /** "2 Jan" by default; the pay page passes its own language's dates. */
  formatDate?: (value: string) => string;
  /** The pay page is itself a yellow moment: the result sits on it, stacked, instead of a card. */
  onPage?: boolean;
  words?: {
    paid: string;
    paidThrough: (date: string) => string;
    autopay: string;
    done: string;
    checking: string;
    confirming: string;
    confirmingDetail: string;
    slow: string;
    failed: string;
    failedDetail: string;
    retry: string;
  };
}) {
  const { receipt, waitedLong } = useReceipt(paymentId, onPaid);
  const failed = paymentId === "unknown" || receipt?.status === "failed" || receipt?.status === "abandoned";

  if (receipt?.status === "paid") {
    return (
      <section
        role="status"
        className={
          onPage
            ? "flex flex-col items-start gap-4 py-4"
            : "moment flex flex-col items-start gap-4 rounded-3xl p-6 sm:flex-row sm:items-center sm:p-8"
        }
      >
        <DrawnCheck />
        <div className="min-w-0 flex-1">
          <h2 className={onPage ? "text-[2.5rem] leading-[1.05] font-extrabold tracking-[-0.045em]" : "text-2xl font-extrabold tracking-[-0.045em]"}>
            {words.paid}
          </h2>
          <p className="mt-1 text-sm leading-relaxed text-sunflower-ink">
            {receipt.covers_to && words.paidThrough(formatDate(receipt.covers_to))}{" "}
            {receipt.autopay && words.autopay}
          </p>
        </div>
        <Button onClick={onDone}>{words.done}</Button>
      </section>
    );
  }
  if (failed) {
    return (
      <section role="alert" className="rounded-3xl border border-amber-200 bg-amber-50 p-5 text-amber-950 sm:p-6">
        <h2 className="text-lg font-semibold">{words.failed}</h2>
        <p className="mt-1 text-sm leading-relaxed">{words.failedDetail}</p>
        <div className="mt-4 flex flex-wrap gap-2">
          <Button onClick={onRetry}>{words.retry}</Button>
          <Button variant="ghost" onClick={onDone}>
            {words.done}
          </Button>
        </div>
      </section>
    );
  }
  return (
    <section role="status" className="surface flex items-start gap-3 rounded-3xl p-5 sm:p-6">
      <LoaderCircle className="mt-0.5 size-5 shrink-0 motion-safe:animate-spin" aria-hidden="true" />
      <div>
        <h2 className="font-semibold">{receipt ? words.confirming : words.checking}</h2>
        {receipt && <p className="mt-1 text-sm leading-relaxed text-ink-soft">{waitedLong ? words.slow : words.confirmingDetail}</p>}
      </div>
    </section>
  );
}
