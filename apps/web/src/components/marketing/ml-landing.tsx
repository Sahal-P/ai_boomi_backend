import { Check, ChevronsRight } from "lucide-react";
import Link from "next/link";

import { Brand } from "@/components/brand";
import { SiteFooter } from "@/components/marketing/final-cta";
import { StartLink, WhatsAppEntryProvider } from "@/components/marketing/start-link";
import { PREMIUM_PRICE } from "@/lib/business";
import { TRIAL_DAYS } from "@/lib/pricing";

const LABELS = {
  chat: "WhatsApp-ൽ തുടങ്ങാം",
  dashboard: "ഡാഷ്ബോർഡ് തുറക്കാം",
  loading: "FinBoy തുറക്കാം",
  web: "തുടങ്ങാം",
};
const ASSURANCES = ["ആപ്പ് വേണ്ട", "ബാങ്ക് ലോഗിൻ വേണ്ട", "ഓരോ എൻട്രിക്കും Undo"] as const;
const STEPS = [
  {
    title: "WhatsApp-ൽ “നമസ്കാരം” അയക്കൂ",
    body: "ബട്ടൺ അമർത്തിയാൽ മെസേജ് തയ്യാറായിരിക്കും. അയച്ചാൽ മതി.",
  },
  {
    title: "ചെലവ് എഴുതൂ, അല്ലെങ്കിൽ പറയൂ",
    body: "“ചായ 20” എന്ന് എഴുതാം, അല്ലെങ്കിൽ ഒരു വോയ്സ് നോട്ട്. ബില്ലിന്റെ ഫോട്ടോയും ആവാം.",
  },
  {
    title: "FinBoy ഉടനെ ചേർത്ത് കാണിക്കും",
    body: "ഓരോന്നും ശരിയായ വിഭാഗത്തിലാക്കും. മാസത്തെ കണക്കിന് “ഈ മാസം” എന്ന് അയക്കൂ.",
  },
] as const;

/**
 * The Malayalam ad page (docs/ad-journey-round/contract.md): the reel's promise in Malayalam on one
 * screen and one WhatsApp button that types "നമസ്കാരം FinBoy", so the welcome comes in Malayalam.
 * No 3D scene, smooth scrolling or glass script, so it opens fast in Instagram's browser.
 */
export function MlLanding({ number }: { number: string | null }) {
  return (
    <WhatsAppEntryProvider language="ml" number={number}>
      <a
        href="#main"
        className="sr-only rounded-full bg-ink px-4 py-3 text-white focus:not-sr-only focus:fixed focus:top-4 focus:left-4 focus:z-50"
      >
        ഉള്ളടക്കത്തിലേക്ക്
      </a>
      <header className="moment px-4 pt-4 sm:px-6">
        <div className="mx-auto flex h-14 max-w-[1360px] items-center justify-between">
          <Brand />
          <Link
            href="/"
            lang="en"
            className="inline-flex h-10 items-center rounded-full bg-white/70 px-4 text-[13px] font-semibold text-ink hover:bg-white/85"
          >
            English · <span lang="hi">&nbsp;हिंदी</span>
          </Link>
        </div>
      </header>
      {/* As on the home page: without isolation-auto, the field's fixed layer would paint over
          the header and footer. */}
      <main id="main" lang="ml" className="bg-field isolation-auto">
        <section aria-labelledby="ml-title" className="moment">
          <div className="mx-auto max-w-[1360px] px-6 pt-8 pb-16 sm:px-10 lg:px-16 lg:pt-16 lg:pb-24">
            <p className="eyebrow inline-flex w-fit items-center gap-2 rounded-full border-2 border-ink bg-white px-3.5 py-1.5 text-ink">
              <span className="size-1.5 rounded-full bg-ink" />
              WhatsApp-ലെ ചെലവ് ഡയറി
            </p>
            <h1
              id="ml-title"
              // "കണക്കുപുസ്തകം," is one word of about 10.6 em: it must fit a 320 px phone whole.
              className="mt-6 max-w-[16ch] text-[1.8rem] leading-[1.2] font-extrabold tracking-[-0.02em] [overflow-wrap:anywhere] text-ink min-[400px]:text-[2.15rem] sm:text-[3.4rem] lg:text-[4.2rem]"
            >
              കണക്കുപുസ്തകം, ഇനി WhatsApp-ൽ.
            </h1>
            <p className="mt-6 text-[1.0625rem] leading-relaxed font-semibold text-ink">
              ചെലവ് മെസേജ് പോലെ അയച്ചാൽ മതി:
            </p>
            <ul className="mt-3 space-y-2 text-[1.0625rem] leading-relaxed text-sunflower-ink">
              <li>
                <span aria-hidden="true">✍️ </span>
                <span className="font-semibold text-ink">ചായ 20, ഓട്ടോ 50</span>
              </li>
              <li>
                <span aria-hidden="true">🎤 </span>അല്ലെങ്കിൽ പറഞ്ഞ് ഒരു വോയ്സ് നോട്ട്
              </li>
            </ul>
            <p className="mt-3 max-w-[34rem] text-[1.0625rem] leading-relaxed text-sunflower-ink">
              FinBoy ഉടനെ ചേർത്ത് വിഭാഗം തിരിക്കും.
            </p>
            <div className="mt-8">
              <StartLink
                labels={LABELS}
                className="group lg-prominent inline-flex h-14 items-center gap-3 rounded-full p-1 pr-7 text-base font-semibold hover:-translate-y-0.5"
                before={
                  <span className="lg-knob grid h-12 w-16 place-items-center rounded-full text-ink transition-transform duration-300 ease-out-expo group-hover:translate-x-0.5">
                    <ChevronsRight className="size-5" aria-hidden="true" />
                  </span>
                }
              />
            </div>
            <ul className="mt-7 flex flex-wrap gap-x-6 gap-y-2 text-sm font-semibold text-sunflower-ink">
              {ASSURANCES.map((item) => (
                <li key={item} className="flex items-center gap-2">
                  <Check className="size-4 text-ink" aria-hidden="true" />
                  {item}
                </li>
              ))}
            </ul>
            <p className="mt-6 max-w-[36rem] text-sm leading-relaxed text-sunflower-ink">
              എഴുതി അയയ്ക്കുന്ന എൻട്രികളും ചോദ്യങ്ങളും സൗജന്യമാണ്. വോയ്സ് നോട്ടും ഫോട്ടോ വായനയും Premium:{" "}
              {TRIAL_DAYS} ദിവസം സൗജന്യം, പിന്നെ മാസം {PREMIUM_PRICE}. കാർഡ് വേണ്ട. തുടരുന്നതിലൂടെ നിങ്ങൾ
              ഞങ്ങളുടെ{" "}
              <Link href="/terms" className="font-semibold text-ink underline underline-offset-4">
                നിബന്ധനകൾ
              </Link>{" "}
              അംഗീകരിക്കുന്നു.
            </p>
          </div>
        </section>
        <section aria-labelledby="ml-steps" className="px-6 py-16 sm:px-10 lg:px-16">
          <div className="mx-auto grid max-w-[1360px] gap-10 lg:grid-cols-[1.2fr_1fr] lg:items-start">
            <div>
              <h2 id="ml-steps" className="text-[1.9rem] leading-tight font-bold text-ink">
                എങ്ങനെ ഉപയോഗിക്കാം
              </h2>
              <ol className="mt-8 space-y-6">
                {STEPS.map((step, index) => (
                  <li key={step.title} className="flex gap-4">
                    <span
                      aria-hidden="true"
                      className="grid size-9 shrink-0 place-items-center rounded-full bg-ink text-sm font-bold text-white"
                    >
                      {index + 1}
                    </span>
                    <div>
                      <p className="font-semibold text-ink">{step.title}</p>
                      <p className="mt-1 leading-relaxed text-ink-soft">{step.body}</p>
                    </div>
                  </li>
                ))}
              </ol>
            </div>
            <figure className="surface rounded-[1.75rem] p-5" aria-label="WhatsApp-ലെ ഒരു ഉദാഹരണം">
              <p className="ml-auto w-fit max-w-[80%] rounded-2xl rounded-tr-md bg-[#d9fdd3] px-4 py-2.5 text-ink">
                ചായ 20
              </p>
              <div className="mt-3 w-fit max-w-[85%] rounded-2xl rounded-tl-md bg-white px-4 py-3 text-ink shadow-sm">
                <p>✅ ചേർത്തു: ₹20 കൊടുത്തു</p>
                <p>🏷️ ഭക്ഷണം</p>
                <p>📅 ഇന്ന്</p>
              </div>
              <figcaption className="mt-4 text-sm text-ink-soft">
                ഓരോ എൻട്രിക്കും താഴെ ↩️ തിരിച്ചെടുക്കാനുള്ള ബട്ടൺ ഉണ്ടാകും.
              </figcaption>
            </figure>
          </div>
        </section>
      </main>
      <SiteFooter />
    </WhatsAppEntryProvider>
  );
}
