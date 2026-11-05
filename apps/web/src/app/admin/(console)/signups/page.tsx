import type { Metadata } from "next";
import { SignupsScreen } from "@/components/admin/signups-screen";

export const metadata: Metadata = { title: "Sign-ups" };

export default function AdminSignupsPage() {
  return <SignupsScreen />;
}
