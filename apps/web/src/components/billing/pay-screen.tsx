"use client";

import { Camera, FileText, LoaderCircle, Lock, MessageCircle, MessageCircleQuestion, Mic } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useId, useState, useSyncExternalStore } from "react";
import { ContactFields } from "@/components/billing/contact-fields";
import { PaymentResult } from "@/components/billing/payment-result";
import { Brand } from "@/components/brand";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { Button } from "@/components/ui/button";
import { type ContactInput, getPayLink, type PayLink, startLinkCheckout } from "@/lib/api/billing";
import { isAbort } from "@/lib/api/http";
import { describeProblem, hasCode, type Problem } from "@/lib/messages";
import { PAY_WORDS, payDate, type PayLanguage } from "@/lib/pay-copy";
import { premiumUntil, rupees } from "@/lib/plan";
import { preconnectPayU, submitToPayU } from "@/lib/payu";

const ICONS = [Mic, MessageCircleQuestion, Camera, FileText] as const;
const LANGUAGES: readonly PayLanguage[] = ["en", "hi", "ml"];
const TOKEN_KEY = "finboy-pay-link";
// The token in memory too, for browsers that refuse session storage.
let remembered: string | null = null;

/** The pay link's token: in the URL fragment when the link is opened, then in this tab only. */
function readToken(): string | null {
  const fromHash = window.location.hash.slice(1);
  if (fromHash) {
    remembered = fromHash;
    return fromHash;
  }
  try {
    return sessionStorage.getItem(TOKEN_KEY) ?? remembered;
  } catch {
    return remembered;
  }
}

/** Keeps the token for this tab and takes it out of the address bar, so it never sits in history
 *  or reaches a server log. */
function keepToken(token: string) {
  try {
    sessionStorage.setItem(TOKEN_KEY, token);
  } catch {
    // Kept in memory instead (readToken).
  }
  history.replaceState(null, "", window.location.pathname + window.location.search);
}

/** Another pay link opened in the same tab changes only the fragment. */
function onHashChange(changed: () => void) {
  window.addEventListener("hashchange", changed);
  return () => window.removeEventListener("hashchange", changed);
}

/**
 * The page a WhatsApp pay link opens: no sign-in, in the chat's language, showing only the price,
 * the trial date and what PayU needs — then straight to PayU, and back here with the result.
 */
export function PayScreen() {
  const payment = useSearchParams().get("payment");
  // Undefined until the browser has been read (the server has no fragment).
  const token = useSyncExternalStore(onHashChange, readToken, () => undefined);
  // Each link starts afresh, with its own language, plan and answers.
  return <PayPage key={token ?? ""} token={token} payment={payment} />;
}

function PayPage({ token, payment }: { token: string | null | undefined; payment: string | null }) {
  const ids = useId();
  const router = useRouter();
  const [link, setLink] = useState<PayLink | null>(null);
  const [refused, setRefused] = useState(false);
  const [contact, setContact] = useState<ContactInput>({});
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  const language: PayLanguage = link?.language ?? "en";
  const words = PAY_WORDS[language];
  const expired = refused || (token === null && !payment);

  useEffect(() => {
    if (!token) return;
    if (window.location.hash) keepToken(token);
    const controller = new AbortController();
    getPayLink(token, controller.signal).then(
      (view) => {
        setLink(view);
        if (view.plan.can_pay) preconnectPayU(view.plan.checkout_origin);
      },
      (error: unknown) => {
        if (isAbort(error)) return;
        if (hasCode(error, "link_expired")) setRefused(true);
        else setProblem(describeProblem(error, PAY_WORDS.en.failedTitle));
      },
    );
    return () => controller.abort();
  }, [token, payment]);

  async function pay() {
    if (!token) return;
    setBusy(true);
    setProblem(null);
    try {
      submitToPayU(await startLinkCheckout(token, contact));
    } catch (error) {
      setBusy(false);
      setProblem(describeProblem(error, words.failedTitle));
    }
  }

  const plan = link?.plan ?? null;
  const until = plan ? premiumUntil(plan) : null;
  const backToChat = link?.whatsapp_number ? `https://wa.me/${link.whatsapp_number}` : null;

  return (
    <main className="moment moment-page min-h-dvh" lang={language}>
      <div className="mx-auto flex min-h-dvh max-w-md flex-col gap-6 px-5 py-10 sm:px-8">
        <Brand />
        {payment ? (
          <>
            <PaymentResult
              paymentId={payment}
              words={words.result}
              formatDate={(value) => payDate(value, language)}
              onPage
              onDone={() => (backToChat ? window.location.assign(backToChat) : router.replace("/pay"))}
              onRetry={() => router.replace("/pay")}
            />
            {backToChat && (
              <Button asChild variant="outline">
                <a href={backToChat}>
                  <MessageCircle aria-hidden="true" /> {words.back}
                </a>
              </Button>
            )}
          </>
        ) : expired ? (
          <div role="alert" className="space-y-3 rounded-3xl bg-white/55 p-5 text-base leading-relaxed">
            {/* An expired link no longer says which language the chat uses, so say it in all three. */}
            {link ? (
              <p>{words.expired}</p>
            ) : (
              LANGUAGES.map((code) => (
                <p key={code} lang={code}>
                  {PAY_WORDS[code].expired}
                </p>
              ))
            )}
          </div>
        ) : !plan ? (
          problem ? (
            <ProblemNotice problem={problem} />
          ) : (
            <p role="status" className="flex items-center gap-2 text-sm text-sunflower-ink">
              <LoaderCircle className="size-4 motion-safe:animate-spin" aria-hidden="true" />
              {words.loading}
            </p>
          )
        ) : (
          <>
            <header>
              <h1 className="text-sm font-semibold tracking-wide text-sunflower-ink uppercase">{words.title}</h1>
              <p className="mt-2 text-[2.75rem] leading-none font-extrabold tracking-[-0.045em] tabular-nums">
                {rupees(plan.price_minor)}
                <span className="text-lg font-semibold tracking-normal"> {words.perMonth}</span>
              </p>
              <p className="mt-3 text-base leading-relaxed text-sunflower-ink">{words.lead}</p>
            </header>
            <ul className="space-y-3">
              {words.benefits.map((text, index) => {
                const Icon = ICONS[index] ?? Mic;
                return (
                  <li key={text} className="flex items-center gap-3 text-base">
                    <span className="grid size-9 shrink-0 place-items-center rounded-full bg-white/55">
                      <Icon className="size-4" aria-hidden="true" />
                    </span>
                    {text}
                  </li>
                );
              })}
            </ul>
            {plan.can_pay ? (
              <form
                className="space-y-4"
                onSubmit={(event) => {
                  event.preventDefault();
                  void pay();
                }}
              >
                {until && new Date(until) > new Date() && (
                  <p className="rounded-2xl bg-white/55 p-3 text-sm leading-relaxed">
                    {plan.state === "trial" && !plan.paid_through
                      ? words.trial(payDate(until, language))
                      : words.next(payDate(until, language))}
                  </p>
                )}
                <ContactFields
                  id={ids}
                  contact={plan.contact}
                  value={contact}
                  onChange={setContact}
                  labels={{ email: words.email, phone: words.phone }}
                  disabled={busy}
                />
                {problem && <ProblemNotice problem={problem} />}
                <Button type="submit" size="lg" className="w-full" disabled={busy}>
                  {busy ? (
                    <>
                      <LoaderCircle className="motion-safe:animate-spin" aria-hidden="true" /> {words.opening}
                    </>
                  ) : (
                    words.pay(rupees(plan.price_minor))
                  )}
                </Button>
                <p className="flex items-start gap-2 text-xs leading-relaxed text-sunflower-ink">
                  <Lock className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
                  <span>
                    {words.secure} {plan.autopay_available && words.autopay}{" "}
                    <Link href="/terms" className="underline underline-offset-2">
                      {words.terms}
                    </Link>{" "}
                    ·{" "}
                    <Link href="/refund-policy" className="underline underline-offset-2">
                      {words.refunds}
                    </Link>
                  </span>
                </p>
              </form>
            ) : (
              <div className="space-y-3">
                <p className="rounded-2xl bg-white/55 p-4 text-base">
                  {until ? words.allSet(payDate(until, language)) : words.allSet("—")}
                </p>
                {backToChat && (
                  <Button asChild>
                    <a href={backToChat}>
                      <MessageCircle aria-hidden="true" /> {words.back}
                    </a>
                  </Button>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </main>
  );
}
