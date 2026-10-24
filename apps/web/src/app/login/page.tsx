import type { Metadata } from "next";
import { HouseholdLogin } from "@/components/app-shell/household-login";
import { safeReturnPath } from "@/lib/api/auth";

export const metadata: Metadata = {
  title: "Sign in",
  robots: { index: false, follow: false },
};

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string | string[] }>;
}) {
  const { next } = await searchParams;
  return <HouseholdLogin next={safeReturnPath(typeof next === "string" ? next : null)} />;
}
