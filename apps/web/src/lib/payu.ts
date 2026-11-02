import { PAYU_ACTIONS, type Checkout } from "./api/billing.ts";

// The browser's only part in a PayU payment: post the form the API signed, as a top-level
// navigation, to one of PayU's two checkout addresses (docs/subscription-round/contract.md).

const allowed = new Set<string>(PAYU_ACTIONS);
const warmed = new Set<string>();

/** Opens the connection to PayU while the person reads the sheet, so its page loads sooner. */
export function preconnectPayU(origin: string) {
  if (typeof document === "undefined" || warmed.has(origin)) return;
  if (!allowed.has(`${origin}/_payment`)) return;
  warmed.add(origin);
  for (const rel of ["preconnect", "dns-prefetch"]) {
    const link = document.createElement("link");
    link.rel = rel;
    link.href = origin;
    document.head.append(link);
  }
}

/**
 * Posts the signed form to PayU. finboy.io sends `Referrer-Policy: no-referrer`, but PayU checks
 * that payments come from the registered website, so only this navigation shares the origin.
 */
export function submitToPayU(checkout: Checkout) {
  if (!allowed.has(checkout.action)) throw new Error("Unexpected payment address");
  const meta = document.querySelector<HTMLMetaElement>('meta[name="referrer"]') ?? document.createElement("meta");
  meta.name = "referrer";
  meta.content = "strict-origin";
  if (!meta.isConnected) document.head.append(meta);
  const form = document.createElement("form");
  form.method = "POST";
  form.action = checkout.action;
  form.acceptCharset = "UTF-8";
  form.hidden = true;
  for (const [name, value] of Object.entries(checkout.fields)) {
    const input = document.createElement("input");
    input.type = "hidden";
    input.name = name;
    input.value = value;
    form.append(input);
  }
  document.body.append(form);
  form.submit();
}
