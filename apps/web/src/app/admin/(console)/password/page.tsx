import type { Metadata } from "next";
import { PasswordScreen } from "@/components/admin/password-screen";

export const metadata: Metadata = { title: "Password" };

export default function AdminPasswordPage() {
  return <PasswordScreen />;
}
