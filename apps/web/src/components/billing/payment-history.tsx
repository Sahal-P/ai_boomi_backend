"use client";

import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { useResource } from "@/hooks/use-resource";
import { listPayments, type Payment } from "@/lib/api/billing";
import { formatDay } from "@/lib/dates";
import { describeProblem } from "@/lib/messages";
import { rupees, shortDate } from "@/lib/plan";

const MODES: Record<string, string> = { UPI: "UPI", CC: "Credit card", DC: "Debit card", NB: "Net banking" };

function Status({ payment }: { payment: Payment }) {
  if (payment.status === "paid") return <Badge variant="positive">Paid</Badge>;
  if (payment.status === "pending") return <Badge variant="warning">Confirming</Badge>;
  return <Badge variant="default">Didn&apos;t go through</Badge>;
}

/** Below the fold, so it loads after the plan itself is on screen. */
export function PaymentHistory({ version }: { version: number }) {
  const payments = useResource(`billing-payments:${version}`, (signal) => listPayments(signal));
  const rows = payments.data?.payments ?? null;
  return (
    <section aria-labelledby="payments-title" className="surface rounded-3xl p-5 sm:p-6">
      <h2 id="payments-title" className="text-lg font-semibold">
        Payments
      </h2>
      {payments.error !== null && !rows && (
        <ProblemNotice className="mt-3" problem={describeProblem(payments.error, "Payments couldn't be loaded")} onRetry={payments.reload} />
      )}
      {!rows && payments.error === null && (
        <div className="mt-3 space-y-2" aria-hidden="true">
          <Skeleton className="h-12 rounded-xl" />
          <Skeleton className="h-12 rounded-xl" />
        </div>
      )}
      {rows && rows.length === 0 && <p className="mt-2 text-sm text-ink-soft">No payments yet.</p>}
      {rows && rows.length > 0 && (
        <ul className="mt-3 divide-y divide-ink/[0.07]">
          {rows.map((payment) => (
            <li key={payment.id} className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 py-3">
              <div className="min-w-0">
                <p className="text-sm font-semibold tabular-nums">
                  {rupees(payment.amount_minor)}
                  <span className="font-normal text-ink-soft">
                    {" "}
                    · {payment.kind === "renewal" ? "AutoPay" : (payment.mode && MODES[payment.mode]) || "PayU"}
                  </span>
                </p>
                <p className="text-xs text-ink-soft">
                  {formatDay(payment.created_at)}
                  {payment.covers_from &&
                    payment.covers_to &&
                    ` · covers ${shortDate(payment.covers_from)} – ${shortDate(payment.covers_to)}`}
                </p>
              </div>
              <Status payment={payment} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
