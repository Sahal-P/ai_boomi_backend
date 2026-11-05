import type { Metadata } from "next";
import { SystemScreen } from "@/components/admin/system-screen";

export const metadata: Metadata = { title: "System" };

export default function AdminSystemPage() {
  return <SystemScreen />;
}
