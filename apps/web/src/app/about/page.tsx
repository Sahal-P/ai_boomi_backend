import Link from "next/link";
import { SeoPage } from "@/components/marketing/seo-page";
import { publicMetadata } from "@/lib/seo/metadata";

export const metadata = publicMetadata("/about", "About", "Meet FinBoy, a money diary built by Sahal P for everyday spending in India.");

export default function AboutPage() {
  return <SeoPage title="About FinBoy">
    <p>FinBoy is a money diary built by Sahal P. It helps people keep track of everyday spending using WhatsApp or the web.</p>
    <h2 className="text-2xl font-semibold">A simple way to remember what you spent</h2>
    <p>You can type an expense, send a voice note, or share a UPI payment screenshot. FinBoy puts the entries together so you can review your spending and budgets. Voice works in English, Hindi and Malayalam.</p>
    <p>FinBoy also supports Google Pay PDF statement imports. It checks the statement totals before saving an import. The information you see depends on what you have recorded and is not a live bank balance.</p>
    <h2 className="text-2xl font-semibold">Your money, your choice</h2>
    <p>You choose what to send. FinBoy has Free and Premium plans, and Gmail import is currently invite-only. Read the <Link className="underline" href="/privacy-policy">Privacy Policy</Link> for details about how information is processed.</p>
    <p>Questions? Email <a className="underline" href="mailto:support@finboy.io">support@finboy.io</a>. You can also find us on <a className="underline" href="https://www.instagram.com/finboyy.io/">Instagram</a>.</p>
  </SeoPage>;
}
