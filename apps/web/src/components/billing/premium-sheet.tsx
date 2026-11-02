"use client";

import { Camera, FileText, LoaderCircle, Lock, MessageCircleQuestion, Mic } from "lucide-react";
import Link from "next/link";
import { useEffect, useId, useState } from "react";
import { ContactFields } from "@/components/billing/contact-fields";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { useMediaQuery } from "@/hooks/use-media-query";
import { type ContactInput, type Plan, startCheckout } from "@/lib/api/billing";
import { describeProblem, type Problem } from "@/lib/messages";
import { FEATURE_LINES, type Feature, premiumUntil, rupees, shortDate, startsLine } from "@/lib/plan";
import { preconnectPayU, submitToPayU } from "@/lib/payu";

export const BENEFITS = [
  { key: "voice", icon: Mic, text: "Voice notes and spoken replies, in English, Hindi and Malayalam" },
  { key: "ask", icon: MessageCircleQuestion, text: "Ask FinBoy anything about your money" },
  { key: "photos", icon: Camera, text: "Photos of bills and UPI screenshots, read for you" },
  { key: "statement", icon: FileText, text: "Months of history from a Google Pay statement" },
] as const;

/**
 * The one upgrade sheet. Opening it warms the connection to PayU; Pay asks the API for a signed
 * form (one small request) and posts it to PayU at once, so the tap goes straight to checkout.
 */
export function PremiumSheet({
  open,
  onOpenChange,
  plan,
  feature,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  plan: Plan;
  feature: Feature | null;
}) {
  const ids = useId();
  const wide = useMediaQuery("(min-width: 640px)");
  const [contact, setContact] = useState<ContactInput>({});
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);

  useEffect(() => {
    if (open) preconnectPayU(plan.checkout_origin);
  }, [open, plan.checkout_origin]);

  async function pay() {
    setBusy(true);
    setProblem(null);
    try {
      submitToPayU(await startCheckout(contact));
      // The page is leaving for PayU; stay busy until it does.
    } catch (error) {
      setBusy(false);
      setProblem(describeProblem(error, "Payment couldn't start"));
    }
  }

  const price = rupees(plan.price_minor);
  const starts = startsLine(plan);
  const until = premiumUntil(plan);

  return (
    <Sheet
      open={open}
      onOpenChange={(next) => {
        if (busy) return;
        onOpenChange(next);
        if (!next) setProblem(null);
      }}
    >
      <SheetContent
        side={wide ? "right" : "bottom"}
        className="gap-0 overflow-y-auto p-0 data-[side=bottom]:max-h-[92dvh] sm:max-w-md"
        aria-describedby={`${ids}-description`}
      >
        <div className="moment rounded-t-3xl px-5 pt-6 pb-5 sm:rounded-none sm:px-6 sm:pt-8">
          <SheetHeader className="p-0">
            <p className="text-xs font-semibold tracking-wide text-sunflower-ink uppercase">FinBoy Premium</p>
            <SheetTitle className="text-[2rem] leading-none font-extrabold tracking-[-0.045em] tabular-nums">
              {price}
              <span className="text-base font-semibold tracking-normal"> / month</span>
            </SheetTitle>
            <SheetDescription id={`${ids}-description`} className="text-sunflower-ink">
              {feature ? FEATURE_LINES[feature] : "Everything FinBoy can do, every day."} Cancel any
              time.
            </SheetDescription>
          </SheetHeader>
        </div>

        <div className="space-y-5 p-5 sm:p-6">
          <ul className="space-y-3" aria-label="What Premium includes">
            {BENEFITS.map(({ key, icon: Icon, text }) => (
              <li key={key} className="flex items-start gap-3 text-sm leading-snug">
                <span className="grid size-8 shrink-0 place-items-center rounded-full bg-ink/[0.06]">
                  <Icon className="size-4" aria-hidden="true" />
                </span>
                <span className={key === feature ? "pt-1.5 font-semibold" : "pt-1.5"}>{text}</span>
              </li>
            ))}
          </ul>

          {plan.can_pay ? (
            <form
              className="space-y-4"
              onSubmit={(event) => {
                event.preventDefault();
                void pay();
              }}
            >
              {starts && <p className="rounded-2xl bg-ink/[0.04] p-3 text-sm leading-relaxed">{starts}</p>}
              <ContactFields id={ids} contact={plan.contact} value={contact} onChange={setContact} disabled={busy} />
              {problem && <ProblemNotice problem={problem} />}
              <Button type="submit" size="lg" className="w-full" disabled={busy}>
                {busy ? (
                  <>
                    <LoaderCircle className="motion-safe:animate-spin" aria-hidden="true" /> Opening PayU…
                  </>
                ) : (
                  `Pay ${price}`
                )}
              </Button>
              <p className="flex items-start gap-2 text-xs leading-relaxed text-ink-soft">
                <Lock className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
                <span>
                  Next: PayU&apos;s secure page — UPI, card or net banking.
                  {plan.autopay_available && " Tick AutoPay there to renew by itself; turn it off any time."}{" "}
                  <Link href="/terms" className="underline underline-offset-2">
                    Terms
                  </Link>{" "}
                  ·{" "}
                  <Link href="/refund-policy" className="underline underline-offset-2">
                    Refunds
                  </Link>
                </span>
              </p>
            </form>
          ) : (
            <div className="space-y-3">
              <p className="rounded-2xl bg-ink/[0.04] p-3 text-sm leading-relaxed">
                {plan.renewal === "autopay"
                  ? "AutoPay renews your Premium by itself."
                  : until
                    ? `You're all set — Premium until ${shortDate(until)}.`
                    : "You're all set."}
              </p>
              <Button asChild variant="outline" className="w-full">
                <Link href="/plan" onClick={() => onOpenChange(false)}>
                  See your plan
                </Link>
              </Button>
            </div>
          )}
        </div>
      </SheetContent>
    </Sheet>
  );
}
