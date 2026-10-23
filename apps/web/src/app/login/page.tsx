import type { Metadata } from "next";
import { HouseholdLogin } from "@/components/app-shell/household-login";

export const metadata: Metadata = { title: "Sign in — FinBoy", robots: { index: false, follow: false } };
export default function LoginPage() { return <HouseholdLogin />; }
