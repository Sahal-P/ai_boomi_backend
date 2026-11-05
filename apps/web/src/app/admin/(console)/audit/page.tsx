import type { Metadata } from "next";
import { Suspense } from "react";
import { AuditScreen } from "@/components/admin/audit-screen";
import { LoadingPanel } from "@/components/feedback/states";

export const metadata: Metadata = { title: "Audit log" };

export default function AdminAuditPage() {
  return (
    <Suspense fallback={<LoadingPanel label="Loading the audit log…" />}>
      <AuditScreen />
    </Suspense>
  );
}
