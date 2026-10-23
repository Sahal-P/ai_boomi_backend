import { ImportClient } from "./import-client";

export default async function ImportPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  return <ImportClient key={runId} runId={runId} />;
}
