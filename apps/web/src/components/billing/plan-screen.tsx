"use client";

import { Check, CheckCircle2, Lock } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useId, useState } from "react";
import { PageHeader } from "@/components/app-shell/page-header";
import { useHouseholdAccess } from "@/components/app-shell/household-context";
import { ContactFields } from "@/components/billing/contact-fields";
import { PaymentHistory } from "@/components/billing/payment-history";
import { PaymentResult } from "@/components/billing/payment-result";
import { usePremium } from "@/components/billing/premium-provider";
import { BENEFITS } from "@/components/billing/premium-sheet";
import { EmptyState } from "@/components/feedback/states";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { AllReviewedArt } from "@/components/illustrations/scenes";
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
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cancelAutopay, type ContactInput, type Plan, updateContact } from "@/lib/api/billing";
import { describeProblem, type Problem } from "@/lib/messages";
import { premiumUntil, rupees, shortDate, statusLine } from "@/lib/plan";
import { preconnectPayU } from "@/lib/payu";

function heroLine(plan: Plan): string {
  const until = premiumUntil(plan);
  if (plan.state === "trial" && !plan.paid_through && until) return `Free trial until ${shortDate(until)}`;
  if (plan.state === "grace") return "Your last payment didn't go through — Premium continues for a few days";
  if (plan.state === "free") return until ? `Premium ended on ${shortDate(until)}` : "You're on the free plan";
  if (plan.renewal === "autopay" && plan.next_charge_on) return `Renews on ${shortDate(plan.next_charge_on)} with AutoPay`;
  return until ? `Paid through ${shortDate(until)}` : "Premium";
}

function Renewal({ plan }: { plan: Plan }) {
  const { updatePlan } = useHouseholdAccess();
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const until = premiumUntil(plan);

  async function turnOff() {
    setBusy(true);
    setProblem(null);
    try {
      updatePlan(await cancelAutopay());
      setConfirming(false);
    } catch (error) {
      setProblem(describeProblem(error, "AutoPay couldn't be turned off"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="renewal-title" className="surface rounded-3xl p-5 sm:p-6">
      <h2 id="renewal-title" className="text-lg font-semibold">
        Renewal
      </h2>
      {plan.renewal === "autopay" ? (
        <>
          <p className="mt-1 text-sm leading-relaxed text-ink-soft">
            AutoPay is on. {rupees(plan.price_minor)} is taken
            {plan.next_charge_on ? ` on ${shortDate(plan.next_charge_on)}` : " each month"}, and your bank tells you two
            days before.
          </p>
          {problem && <ProblemNotice className="mt-3" problem={problem} />}
          <Button variant="outline" className="mt-4" onClick={() => setConfirming(true)}>
            Turn off AutoPay
          </Button>
          <AlertDialog open={confirming} onOpenChange={(open) => !busy && setConfirming(open)}>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>Turn off AutoPay?</AlertDialogTitle>
                <AlertDialogDescription>
                  Nothing more will be taken. Premium stays until {until ? shortDate(until) : "the end of this month"};
                  you can pay again any time.
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel disabled={busy}>Keep AutoPay</AlertDialogCancel>
                <AlertDialogAction
                  variant="destructive"
                  disabled={busy}
                  onClick={(event) => {
                    event.preventDefault();
                    void turnOff();
                  }}
                >
                  {busy ? "Turning off…" : "Turn off AutoPay"}
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </>
      ) : (
        <p className="mt-1 text-sm leading-relaxed text-ink-soft">
          {plan.renewal === "off"
            ? `AutoPay is off. ${until ? `Premium lasts until ${shortDate(until)}; ` : ""}pay again any time.`
            : `You pay one month at a time, and FinBoy reminds you a week before it runs out.`}
          {plan.autopay_available && " To renew by itself, tick AutoPay on PayU's page when you next pay."}
        </p>
      )}
    </section>
  );
}

function Receipts({ plan }: { plan: Plan }) {
  const { updatePlan } = useHouseholdAccess();
  const ids = useId();
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState<ContactInput>({});
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);

  async function save() {
    setBusy(true);
    setProblem(null);
    try {
      updatePlan({ ...plan, contact: await updateContact(value) });
      setEditing(false);
      setValue({});
    } catch (error) {
      setProblem(describeProblem(error, "The email wasn't changed"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="receipts-title" className="surface rounded-3xl p-5 sm:p-6">
      <h2 id="receipts-title" className="text-lg font-semibold">
        Receipts
      </h2>
      <dl className="mt-2 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
        <dt className="text-ink-soft">Email</dt>
        <dd className="break-all">{plan.contact.email ?? "Not added yet"}</dd>
        <dt className="text-ink-soft">Phone</dt>
        <dd>
          {plan.contact.phone ?? "Not added yet"}
          {plan.contact.phone_from_whatsapp && <span className="text-ink-soft"> (your WhatsApp)</span>}
        </dd>
      </dl>
      {editing ? (
        <form
          className="mt-4 space-y-3"
          onSubmit={(event) => {
            event.preventDefault();
            void save();
          }}
        >
          <ContactFields
            id={ids}
            contact={{ ...plan.contact, email: null }}
            value={value}
            onChange={setValue}
            labels={{ email: "New email for receipts", phone: "Mobile number" }}
            disabled={busy}
          />
          {problem && <ProblemNotice problem={problem} />}
          <div className="flex gap-2">
            <Button type="submit" disabled={busy || !value.email?.trim()}>
              {busy ? "Saving…" : "Save"}
            </Button>
            <Button type="button" variant="ghost" onClick={() => setEditing(false)} disabled={busy}>
              Cancel
            </Button>
          </div>
        </form>
      ) : (
        <Button variant="outline" className="mt-4" onClick={() => setEditing(true)}>
          {plan.contact.email ? "Change email" : "Add email"}
        </Button>
      )}
      <p className="mt-3 text-xs leading-relaxed text-ink-soft">
        PayU needs these for every payment. FinBoy keeps them encrypted and deletes them with your account.
      </p>
    </section>
  );
}

/** Account menu → Plan: where the household sees, pays for and manages FinBoy Premium. */
export function PlanScreen() {
  const { plan, refresh } = useHouseholdAccess();
  const premium = usePremium();
  const router = useRouter();
  const params = useSearchParams();
  const payment = params.get("payment");
  const [paidVersion, setPaidVersion] = useState(0);

  useEffect(() => {
    if (plan?.can_pay) preconnectPayU(plan.checkout_origin);
  }, [plan?.can_pay, plan?.checkout_origin]);

  if (!plan) {
    return (
      <div className="space-y-5">
        <PageHeader title="Your plan" />
        <EmptyState illustration={<AllReviewedArt />} title="Everything is included">
          Every FinBoy feature is available to your household. There is nothing to pay.
        </EmptyState>
      </div>
    );
  }

  const included = plan.state === "included";
  return (
    <div className="space-y-5">
      <PageHeader
        title="Your plan"
        description={included ? "FinBoy Premium" : `FinBoy Premium · ${rupees(plan.price_minor)} a month · cancel any time`}
      />
      {payment && (
        <PaymentResult
          paymentId={payment}
          onPaid={() => {
            void refresh();
            setPaidVersion((value) => value + 1);
          }}
          onDone={() => router.replace("/plan")}
          onRetry={() => {
            router.replace("/plan");
            premium.open();
          }}
        />
      )}
      {included ? (
        <section className="surface flex items-start gap-3 rounded-3xl p-5 sm:p-6">
          <CheckCircle2 className="mt-0.5 size-5 shrink-0 text-positive" aria-hidden="true" />
          <p className="text-sm leading-relaxed">Premium is included for your household. There is nothing to pay.</p>
        </section>
      ) : (
        <section aria-labelledby="plan-hero" className="solid-hero rounded-3xl p-5 sm:p-8">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-semibold">FinBoy Premium</p>
            <Badge className="bg-white/60 text-ink">{statusLine(plan)}</Badge>
          </div>
          <p id="plan-hero" className="mt-3 text-[2.5rem] leading-none font-extrabold tracking-[-0.045em] tabular-nums">
            {rupees(plan.price_minor)}
            <span className="text-lg font-semibold tracking-normal"> / month</span>
          </p>
          <p className="mt-2 text-sm text-sunflower-ink">{heroLine(plan)}</p>
          {plan.can_pay && (
            <Button size="lg" className="mt-5" onClick={() => premium.open()}>
              Pay {rupees(plan.price_minor)}
            </Button>
          )}
        </section>
      )}

      <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-2">
        <section aria-labelledby="included-title" className="surface rounded-3xl p-5 sm:p-6">
          <h2 id="included-title" className="text-lg font-semibold">
            {plan.premium ? "What's included" : "What Premium adds"}
          </h2>
          <ul className="mt-3 space-y-3">
            {BENEFITS.map(({ key, text }) => (
              <li key={key} className="flex items-start gap-3 text-sm leading-snug">
                {plan.premium ? (
                  <Check className="mt-0.5 size-4 shrink-0 text-positive" aria-hidden="true" />
                ) : (
                  <Lock className="mt-0.5 size-4 shrink-0 text-ink-soft" aria-hidden="true" />
                )}
                {text}
              </li>
            ))}
          </ul>
          <p className="mt-4 text-xs leading-relaxed text-ink-soft">
            Always free: typed entries on the web and WhatsApp, Home, Transactions, Reports, budgets and your
            savings goal.
          </p>
        </section>
        {!included && <Renewal plan={plan} />}
        {!included && <Receipts plan={plan} />}
        {!included && <PaymentHistory version={paidVersion} />}
      </div>

      {!included && (
        <p className="text-center text-xs text-ink-soft">
          <Link href="/refund-policy" className="underline underline-offset-2">
            Refunds and cancellation
          </Link>{" "}
          ·{" "}
          <Link href="/terms" className="underline underline-offset-2">
            Terms
          </Link>{" "}
          ·{" "}
          <Link href="/contact" className="underline underline-offset-2">
            Contact
          </Link>
        </p>
      )}
    </div>
  );
}
