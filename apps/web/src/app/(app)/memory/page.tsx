import type { Metadata } from "next";
import { MemoryScreen } from "@/components/memory/memory-screen";

export const metadata: Metadata = { title: "Memory" };

export default function MemoryPage() {
  return <MemoryScreen />;
}
