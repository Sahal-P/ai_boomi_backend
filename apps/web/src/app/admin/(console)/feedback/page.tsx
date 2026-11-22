import type { Metadata } from "next";
import { Suspense } from "react";
import { FeedbackScreen } from "@/components/admin/feedback-screen";
import { LoadingPanel } from "@/components/feedback/states";

export const metadata: Metadata = { title: "Feedback" };

export default function AdminFeedbackPage() {
  return (
    <Suspense fallback={<LoadingPanel label="Loading feedback…" />}>
      <FeedbackScreen />
    </Suspense>
  );
}
