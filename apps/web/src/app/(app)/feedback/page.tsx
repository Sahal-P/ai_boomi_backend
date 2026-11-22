import type { Metadata } from "next";
import { Suspense } from "react";
import { LoadingPanel } from "@/components/feedback/states";
import { FeedbackScreen } from "@/components/send-feedback/feedback-screen";

export const metadata: Metadata = { title: "Send feedback" };

export default function FeedbackPage() {
  return (
    <Suspense fallback={<LoadingPanel label="Loading…" />}>
      <FeedbackScreen />
    </Suspense>
  );
}
