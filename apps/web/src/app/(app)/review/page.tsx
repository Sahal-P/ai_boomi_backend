import type { Metadata } from "next";
import { Suspense } from "react";
import { LoadingPanel } from "@/components/feedback/states";
import { ReviewScreen } from "@/components/records/review-screen";

export const metadata: Metadata = { title: "Review" };

export default function ReviewPage() {
  return (
    <Suspense fallback={<LoadingPanel label="Loading records to review…" />}>
      <ReviewScreen />
    </Suspense>
  );
}
