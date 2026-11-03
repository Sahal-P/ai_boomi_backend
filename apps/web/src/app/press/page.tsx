import Link from "next/link";
import { SeoPage } from "@/components/marketing/seo-page";
import { publicMetadata } from "@/lib/seo/metadata";

export const metadata = publicMetadata("/press", "Press resources", "Product information and brand assets for people writing about FinBoy.");

export default function PressPage() {
  return <SeoPage title="Press resources">
    <p>Writing about FinBoy? Here are the basics and a few resources to help you get to know the product.</p>
    <h2 className="text-2xl font-semibold">What is FinBoy?</h2>
    <p>FinBoy is an expense diary for India, built by Sahal P. People can record expenses through WhatsApp or the web, use voice in English, Hindi or Malayalam, and review budgets and reports. Supported Google Pay PDF statements can also be imported.</p>
    <p>FinBoy offers Free and Premium plans. <Link className="underline" href="/pricing">See current pricing</Link> and <Link className="underline" href="/privacy-policy">read the Privacy Policy</Link> for more detail.</p>
    <h2 className="text-2xl font-semibold">Try the sample</h2>
    <p>The <Link className="underline" href="/demo">sample household</Link> uses synthetic data and is available without signing in. It is a read-only demonstration.</p>
    <h2 className="text-2xl font-semibold">Brand assets</h2>
    <p>Download the <a className="underline" href="/brand/finboy-logo-dark.svg" download>FinBoy logo</a> or the <a className="underline" href="/brand/finboy-icon-512.png" download>square icon</a>.</p>
    <h2 className="text-2xl font-semibold">Get in touch</h2>
    <p>For questions or a product walkthrough, email <a className="underline" href="mailto:support@finboy.io">support@finboy.io</a>.</p>
  </SeoPage>;
}
