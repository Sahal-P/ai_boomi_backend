import type { Metadata } from "next";
import { ImportResult } from "@/components/sources/import-result";

export const metadata: Metadata = { title: "Import results" };

export default async function ImportPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  return <ImportResult key={runId} runId={runId} />;
}
