import { z } from "zod";
import { jsonBody, requestJson } from "./http.ts";

// FinBoy Premium (docs/subscription-round/contract.md). The PayU salt never reaches the browser;
// the API returns a form it has already signed, and the browser only posts it to PayU.

const instant = z.iso.datetime({ offset: true });
export const PAYU_ACTIONS = ["https://test.payu.in/_payment", "https://secure.payu.in/_payment"] as const;

export const planSchema = z.object({
  state: z.enum(["included", "trial", "active", "grace", "free"]),
  premium: z.boolean(),
  trial_ends_at: instant.nullable(),
  paid_through: instant.nullable(),
  renewal: z.enum(["manual", "autopay", "off"]).nullable(),
  next_charge_on: z.iso.date().nullable(),
  grace_until: instant.nullable(),
  price_minor: z.number().int().positive(),
  can_pay: z.boolean(),
  autopay_available: z.boolean(),
  checkout_origin: z.enum(["https://test.payu.in", "https://secure.payu.in"]),
  contact: z.object({
    // Masked by the API: "s•••@example.in", "•••• 4821".
    email: z.string().max(80).nullable(),
    phone: z.string().max(40).nullable(),
    phone_from_whatsapp: z.boolean(),
  }),
});
export type Plan = z.infer<typeof planSchema>;

const checkoutSchema = z.object({
  payment_id: z.uuid(),
  action: z.enum(PAYU_ACTIONS),
  fields: z.record(z.string().regex(/^[A-Za-z0-9_]{1,32}$/), z.string().max(2048)),
});
export type Checkout = z.infer<typeof checkoutSchema>;

const receiptSchema = z.object({
  status: z.enum(["started", "scheduled", "pending", "paid", "failed", "abandoned"]),
  covers_to: instant.nullable(),
  autopay: z.boolean(),
});
export type Receipt = z.infer<typeof receiptSchema>;

const paymentSchema = z.object({
  id: z.uuid(),
  kind: z.enum(["checkout", "renewal"]),
  status: z.enum(["pending", "paid", "failed"]),
  amount_minor: z.number().int().positive(),
  mode: z.string().max(12).nullable(),
  autopay: z.boolean(),
  covers_from: instant.nullable(),
  covers_to: instant.nullable(),
  created_at: instant,
});
export type Payment = z.infer<typeof paymentSchema>;

const linkSchema = z.object({
  language: z.enum(["en", "hi", "ml"]),
  plan: planSchema,
  whatsapp_number: z
    .string()
    .regex(/^[0-9]{7,20}$/)
    .nullable(),
});
export type PayLink = z.infer<typeof linkSchema>;

export type ContactInput = { email?: string | undefined; phone?: string | undefined };

function contactBody(contact: ContactInput) {
  return {
    ...(contact.email?.trim() ? { email: contact.email.trim() } : {}),
    ...(contact.phone?.trim() ? { phone: contact.phone.trim() } : {}),
  };
}

export const startCheckout = (contact: ContactInput) =>
  requestJson("/api/v1/billing/checkout", checkoutSchema, { method: "POST", ...jsonBody(contactBody(contact)) });

export const getReceipt = (paymentId: string, signal?: AbortSignal) =>
  requestJson("/api/v1/billing/receipt", receiptSchema, {
    method: "POST",
    ...jsonBody({ payment_id: paymentId }),
    signal,
    // A pending UPI payment may be checked with PayU on the way.
    timeoutMs: 15_000,
  });

export const listPayments = (signal?: AbortSignal) =>
  requestJson("/api/v1/billing/payments", z.object({ payments: z.array(paymentSchema).max(24) }), { signal });

export const updateContact = (contact: ContactInput) =>
  requestJson("/api/v1/billing/contact", planSchema.shape.contact, {
    method: "PATCH",
    ...jsonBody(contactBody(contact)),
  });

export const cancelAutopay = () =>
  requestJson("/api/v1/billing/autopay/cancel", planSchema, { method: "POST", timeoutMs: 20_000 });

export const getPayLink = (token: string, signal?: AbortSignal) =>
  requestJson("/api/v1/billing/link", linkSchema, { method: "POST", ...jsonBody({ token }), signal });

export const startLinkCheckout = (token: string, contact: ContactInput) =>
  requestJson("/api/v1/billing/link/checkout", checkoutSchema, {
    method: "POST",
    ...jsonBody({ token, ...contactBody(contact) }),
  });
