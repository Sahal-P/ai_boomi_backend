import type { Metadata } from "next";
import { Suspense } from "react";
import { MessagesScreen } from "@/components/admin/messages-screen";
import { LoadingPanel } from "@/components/feedback/states";

export const metadata: Metadata = { title: "Messages" };

export default function AdminMessagesPage() {
  return (
    <Suspense fallback={<LoadingPanel label="Loading messages…" />}>
      <MessagesScreen />
    </Suspense>
  );
}
