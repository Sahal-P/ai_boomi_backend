import type { Metadata } from "next";
import { PrivacyScreen } from "@/components/privacy/privacy-screen";

export const metadata: Metadata = { title: "Privacy & data" };

export default function PrivacyPage() {
  return <PrivacyScreen />;
}
