"use client";

import { Download } from "lucide-react";
import { useState } from "react";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { Button } from "@/components/ui/button";
import { useAction } from "@/hooks/use-action";
import { exportRecords } from "@/lib/api/privacy";

function save(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.rel = "noopener";
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1_000);
}

/** Downloads the structured export only when the person presses it. */
export function ExportButton({
  version,
  onConflict,
  variant = "outline",
}: {
  version: string | null;
  onConflict?: () => void;
  variant?: "outline" | "default";
}) {
  const action = useAction();
  const [done, setDone] = useState<string | null>(null);
  return (
    <div className="space-y-2">
      <Button
        variant={variant}
        disabled={!version || action.busy !== null}
        onClick={async () => {
          if (!version) return;
          setDone(null);
          const file = await action.run("export", "Your records weren't exported", () => exportRecords(version));
          if (file) {
            save(file.blob, file.filename);
            setDone(`Saved ${file.filename} with ${file.transactionCount} records.`);
          } else onConflict?.();
        }}
      >
        <Download aria-hidden="true" /> {action.busy ? "Preparing your file…" : "Download my records (JSON)"}
      </Button>
      <div role="status" aria-live="polite">
        {done && <p className="text-sm text-ink-soft">{done}</p>}
      </div>
      {action.problem && <ProblemNotice problem={action.problem} />}
    </div>
  );
}
