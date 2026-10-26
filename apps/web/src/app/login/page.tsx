import type { Metadata, Viewport } from "next";
import { HouseholdLogin } from "@/components/app-shell/household-login";
import { safeReturnPath } from "@/lib/api/auth";

export const metadata: Metadata = {
  title: "Sign in",
  robots: { index: false, follow: false },
};

// Sign-in is a yellow moment; the phone's browser chrome matches it.
export const viewport: Viewport = { themeColor: "#fed234" };

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string | string[] }>;
}) {
  const { next } = await searchParams;
  return <HouseholdLogin next={safeReturnPath(typeof next === "string" ? next : null)} />;
}
