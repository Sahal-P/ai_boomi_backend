import type { Metadata } from "next";
import { AssistantScreen } from "@/components/assistant/assistant-screen";

export const metadata: Metadata = { title: "Ask FinBoy" };

export default function AssistantPage() {
  return <AssistantScreen />;
}
