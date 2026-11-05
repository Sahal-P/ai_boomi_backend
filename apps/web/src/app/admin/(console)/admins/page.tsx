import type { Metadata } from "next";
import { AdminsScreen } from "@/components/admin/admins-screen";

export const metadata: Metadata = { title: "Admins" };

export default function AdminAccountsPage() {
  return <AdminsScreen />;
}
