import type { Metadata } from "next";
import { Suspense } from "react";
import { AssistantScreen } from "@/components/assistant/assistant-screen";
import { LoadingPanel } from "@/components/feedback/states";

export const metadata: Metadata = { title: "Ask FinBoy" };

// Suspense: Ask reads a question handed over in its address (`?ask=`, from Home's "For you").
export default function AssistantPage() {
  return (
    <Suspense fallback={<LoadingPanel label="Opening Ask FinBoy…" />}>
      <AssistantScreen />
    </Suspense>
  );
}
