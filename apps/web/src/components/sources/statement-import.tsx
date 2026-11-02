"use client";

import { FileText } from "lucide-react";
import { useRouter } from "next/navigation";
import { useId, useRef, useState } from "react";
import { useHouseholdAccess } from "@/components/app-shell/household-context";
import { PremiumPill } from "@/components/billing/premium-pill";
import { usePremium } from "@/components/billing/premium-provider";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { formatBytes } from "@/hooks/use-staged-upload";
import { isAbort } from "@/lib/api/http";
import { statementFileProblem, uploadStatement, type StatementFileProblem } from "@/lib/api/imports";
import { describeProblem, hasCode, type Problem } from "@/lib/messages";

const fileCopy: Record<StatementFileProblem, string> = {
  not_pdf: "That isn't a PDF. Choose the statement Google Pay saved — its name ends in .pdf.",
  empty: "That file is empty. Download the statement from Google Pay again.",
  too_large: "That file is larger than 10 MB. Download a shorter period, a year at most.",
};

function uploadProblem(error: unknown): Problem {
  const problem = describeProblem(error, "Your statement wasn't imported");
  // The shared copy for this code talks about email batches.
  return hasCode(error, "upload_limit")
    ? { ...problem, detail: "This statement is too long for one import. Download a year or less at a time." }
    : problem;
}

/**
 * Choose one Google Pay statement PDF; FinBoy reads and checks it, then shows the import's result.
 * The file is read in memory on the server and never stored.
 */
export function StatementImport() {
  const router = useRouter();
  const { signIn } = useHouseholdAccess();
  const input = useRef<HTMLInputElement>(null);
  const premium = usePremium();
  const control = useRef<AbortController | null>(null);
  const headingId = useId();
  const [file, setFile] = useState<File | null>(null);
  const [progress, setProgress] = useState<number | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const uploading = progress !== null;

  async function upload(chosen: File) {
    setFile(chosen);
    const local = statementFileProblem(chosen);
    if (local) {
      setProblem({ title: "This file can't be imported", detail: fileCopy[local], reference: null, kind: "validation", code: null });
      return;
    }
    const controller = new AbortController();
    control.current = controller;
    setProblem(null);
    setProgress(0);
    try {
      const started = await uploadStatement(chosen, { signal: controller.signal, onProgress: setProgress });
      router.push(`/import/${started.import_run_id}`);
    } catch (error) {
      setProblem(
        isAbort(error)
          ? { title: "Upload cancelled", detail: "Nothing was imported.", reference: null, kind: "unknown", code: null }
          : uploadProblem(error),
      );
    } finally {
      control.current = null;
      setProgress(null);
    }
  }

  return (
    <section aria-labelledby={headingId} id="statement" className="surface scroll-mt-24 rounded-3xl p-5 sm:p-6">
      <div className="flex items-start gap-3">
        <span className="grid size-10 shrink-0 place-items-center rounded-full bg-white/80 text-ink ring-1 ring-ink/[0.06]">
          <FileText className="size-5" aria-hidden="true" />
        </span>
        <div className="min-w-0">
          <h2 id={headingId} className="text-lg font-semibold">
            Import a Google Pay statement
          </h2>
          <p className="mt-1 text-sm leading-relaxed text-ink-soft">
            Bring in months of payments at once. FinBoy checks every row against the statement&apos;s own
            totals and keeps each payment&apos;s name, time and UPI transaction ID. The PDF is read once and
            never stored.
          </p>
        </div>
      </div>

      <details className="mt-4 rounded-2xl bg-well px-4 py-3 text-sm ring-1 ring-ink/5">
        <summary className="cursor-pointer font-semibold text-ink">How do I get my statement?</summary>
        <ol className="mt-2 list-decimal space-y-1 pl-5 leading-relaxed text-ink-soft">
          <li>Open Google Pay and scroll down to See transaction history.</li>
          <li>Tap More (⋮) at the top right, then Get statement.</li>
          <li>Choose the months you want, tap Continue and save the PDF.</li>
        </ol>
        <p className="mt-2 leading-relaxed text-ink-soft">
          Menu names can differ a little between app versions. Payments made in other apps aren&apos;t in a
          Google Pay statement.
          {signIn?.whatsapp && " You can also send the PDF to FinBoy on WhatsApp."}
        </p>
      </details>

      <input
        ref={input}
        type="file"
        accept=".pdf,application/pdf"
        hidden
        onChange={(event) => {
          const chosen = event.target.files?.[0];
          event.target.value = "";
          if (chosen) void upload(chosen);
        }}
      />
      {uploading ? (
        <div className="mt-4 space-y-2">
          <div className="flex items-center justify-between gap-3 text-sm font-medium">
            <span role="status" className="min-w-0 truncate">
              Sending {file?.name ?? "your statement"}… {Math.round((progress ?? 0) * 100)}%
            </span>
            <Button type="button" variant="ghost" size="sm" onClick={() => control.current?.abort()}>
              Cancel
            </Button>
          </div>
          <Progress value={Math.round((progress ?? 0) * 100)} aria-label="Upload progress" className="h-1.5" />
          {progress === 1 && <p className="text-xs text-ink-soft">Reading every page and checking the totals…</p>}
        </div>
      ) : (
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <Button type="button" onClick={() => premium.guard("statement", () => input.current?.click())}>
            <FileText aria-hidden="true" /> Choose statement PDF
            {!premium.premium && <PremiumPill />}
          </Button>
          {file && problem && (
            <span className="min-w-0 truncate text-xs text-ink-soft">
              {file.name} · {formatBytes(file.size)}
            </span>
          )}
        </div>
      )}
      {problem && <ProblemNotice className="mt-4" problem={problem} />}
    </section>
  );
}
