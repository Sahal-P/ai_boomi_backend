"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useId, useState } from "react";
import { count, day, moment, Pager, RefreshButton } from "@/components/admin/admin-bits";
import { PageHeader } from "@/components/app-shell/page-header";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { LoadingPanel, RefreshingLabel } from "@/components/feedback/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useAction } from "@/hooks/use-action";
import { useQueryUpdate } from "@/hooks/use-query-update";
import { useResource } from "@/hooks/use-resource";
import { paymentStatusLabels } from "@/lib/admin-labels";
import { listAdminPayments, PAYMENT_STATUSES, reconcilePayment, type AdminPayment, type PaymentStatus } from "@/lib/api/admin";
import { describeProblem } from "@/lib/messages";
import { rupees } from "@/lib/plan";

const OPEN = new Set<PaymentStatus>(["started", "scheduled", "pending"]);
const MODES: Record<string, string> = { UPI: "UPI", CC: "Credit card", DC: "Debit card", NB: "Net banking" };

function StatusBadge({ status }: { status: PaymentStatus }) {
  const variant = status === "paid" ? "positive" : OPEN.has(status) ? "warning" : "default";
  return <Badge variant={variant}>{paymentStatusLabels[status]}</Badge>;
}

function PaymentItem({
  payment,
  busy,
  locked,
  onCheck,
}: {
  payment: AdminPayment;
  /** This payment is being re-checked. */
  busy: boolean;
  /** Another re-check is running. */
  locked: boolean;
  onCheck: (() => void) | null;
}) {
  return (
    <li className="surface rounded-lg px-4 py-3">
      <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-1">
        <p className="text-sm tabular-nums">
          <strong>{rupees(payment.amount_minor)}</strong>
          <span className="text-ink-soft">
            {" "}
            · {payment.kind === "renewal" ? "AutoPay renewal" : "Checkout"}
            {payment.mode ? ` · ${MODES[payment.mode] ?? payment.mode}` : ""}
          </span>
        </p>
        <StatusBadge status={payment.status} />
      </div>
      <p className="mt-1 text-xs text-ink-soft">
        {moment(payment.created_at)} · household{" "}
        <Link
          href={`/admin/households?selected=${payment.household_id}`}
          className="font-mono font-semibold text-ink underline underline-offset-4"
        >
          {payment.short_id}
        </Link>
        {payment.covers_to ? ` · covers to ${day(payment.covers_to)}` : ""}
      </p>
      <p className="mt-1 font-mono text-[11px] break-all text-ink-soft">
        {payment.txnid}
        {payment.payu_id ? ` · PayU ${payment.payu_id}` : ""}
        {payment.error_code ? ` · ${payment.error_code}` : ""}
      </p>
      {onCheck && (
        <Button size="sm" variant="outline" className="mt-2" disabled={busy || locked} onClick={onCheck}>
          {busy ? "Asking PayU…" : "Re-check with PayU"}
        </Button>
      )}
    </li>
  );
}

/** FinBoy's own sales records; no card numbers, UPI IDs or bank references exist to show. */
export function PaymentsScreen() {
  const params = useSearchParams();
  const update = useQueryUpdate();
  const ids = useId();
  const status = PAYMENT_STATUSES.find((value) => value === params.get("status")) ?? null;
  const offsetParam = Number(params.get("offset") ?? 0);
  const offset = Number.isInteger(offsetParam) && offsetParam > 0 ? offsetParam : 0;
  const payments = useResource(`admin-payments:${status ?? "all"}:${offset}`, (signal) => listAdminPayments(status, offset, signal));
  const check = useAction();
  const [announcement, setAnnouncement] = useState("");
  const page = payments.stale ? null : payments.data;

  async function recheck(payment: AdminPayment) {
    const result = await check.run(payment.id, "The payment wasn't re-checked", () => reconcilePayment(payment.id));
    if (!result || !page) return;
    payments.replace({ ...page, items: page.items.map((item) => (item.id === result.id ? result : item)) });
    setAnnouncement(`PayU says ${payment.txnid} is ${paymentStatusLabels[result.status].toLowerCase()}.`);
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Payments"
        description="FinBoy's own ₹299 sales: when, how and whether they went through. Card numbers, UPI IDs and bank references are never kept."
        actions={<RefreshButton resource={payments} />}
      />
      <div className="max-w-xs">
        <label htmlFor={`${ids}-status`} className="text-xs font-semibold">
          Status
        </label>
        <select
          id={`${ids}-status`}
          className="field field-select mt-1.5 block h-11 w-full rounded-lg pl-3 text-sm"
          value={status ?? ""}
          onChange={(event) => update({ status: event.target.value || null, offset: null })}
        >
          <option value="">All payments</option>
          {PAYMENT_STATUSES.map((value) => (
            <option key={value} value={value}>
              {paymentStatusLabels[value]}
            </option>
          ))}
        </select>
      </div>
      <div role="status" aria-live="polite" className="text-sm font-medium">
        {announcement}
      </div>
      {check.problem && <ProblemNotice problem={check.problem} />}
      <RefreshingLabel active={payments.status === "refreshing"}>Updating payments…</RefreshingLabel>
      {payments.status === "loading" && <LoadingPanel label="Loading payments…" />}
      {payments.error !== null && (
        <ProblemNotice
          problem={describeProblem(payments.error, payments.data ? "Couldn't refresh — showing the last loaded payments" : "Payments couldn't be loaded")}
          onRetry={payments.reload}
        />
      )}
      {page && (
        <section aria-labelledby={`${ids}-title`}>
          <h2 id={`${ids}-title`} className="text-base font-semibold">
            {count(page.total)} {page.total === 1 ? "payment" : "payments"}
          </h2>
          {page.items.length === 0 ? (
            <p className="mt-2 text-sm text-ink-soft">{status ? "No payments in this state." : "No payments yet."}</p>
          ) : (
            <ul aria-label="Payments" className="mt-3 space-y-2">
              {page.items.map((payment) => (
                <PaymentItem
                  key={payment.id}
                  payment={payment}
                  busy={check.busy === payment.id}
                  locked={check.busy !== null}
                  onCheck={OPEN.has(payment.status) ? () => void recheck(payment) : null}
                />
              ))}
            </ul>
          )}
          <Pager
            label="Payment pages"
            offset={page.offset}
            shown={page.items.length}
            total={page.total}
            nextOffset={page.next_offset}
            onPage={(next) => update({ offset: next ? String(next) : null })}
          />
        </section>
      )}
    </div>
  );
}
