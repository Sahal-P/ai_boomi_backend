"use client";

import { ImportScreen } from "@/components/mail/import-screen";
import { useImportRun } from "@/hooks/use-import-run";

export function ImportClient({ runId }: { runId: string }) {
  const { run, error, refresh } = useImportRun(runId);
  return <ImportScreen run={run} error={error} onRetry={refresh} />;
}
