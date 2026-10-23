import Link from "next/link";
import { ShieldCheck } from "lucide-react";

export function MailFrame({ eyebrow, title, description, children }: {
  eyebrow: string; title: string; description: string; children: React.ReactNode;
}) {
  return <section className="mx-auto w-full max-w-5xl px-5 py-10 sm:px-8 sm:py-14">
    <div className="mb-9 flex items-center justify-between gap-4 text-sm">
      <Link href="/connect" className="font-semibold tracking-tight">FinBoy <span className="font-normal text-muted-foreground">/ email & trust</span></Link>
      <Link href="/privacy" className="flex items-center gap-2 text-primary"><ShieldCheck className="size-4" /> Your privacy</Link>
    </div>
    <p className="eyebrow mb-3 uppercase text-primary">{eyebrow}</p>
    <h1 className="max-w-2xl text-3xl leading-tight font-medium tracking-tight sm:text-5xl">{title}</h1>
    <p className="mt-4 max-w-2xl text-base leading-relaxed text-muted-foreground">{description}</p>
    <div className="mt-9">{children}</div>
  </section>;
}

export function MailAlert({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return <div role="alert" className="mb-5 rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm leading-relaxed text-amber-950">
    {message} {onRetry && <button type="button" className="ml-2 font-semibold underline underline-offset-4" onClick={onRetry}>Try again</button>}
  </div>;
}
