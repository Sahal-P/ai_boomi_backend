"use client";

import { FileUp, Mail, X } from "lucide-react";
import { useId, useRef } from "react";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { Button } from "@/components/ui/button";
import { Progress } from "@/components/ui/progress";
import { formatBytes, useStagedUpload } from "@/hooks/use-staged-upload";
import { UPLOAD_LIMITS, type FileProblem } from "@/lib/api/imports";
import { cn } from "@/lib/utils";

const problemCopy: Record<FileProblem, string> = {
  not_eml: "Not an .eml email file",
  empty: "The file is empty",
  too_large: "Larger than 2 MB",
};

/**
 * Stage → check → explicit Import. Used for first uploads and for retrying failed uploaded
 * emails, which needs the original files because FinBoy never stores uploaded emails.
 */
export function UploadStager({ retryCount }: { retryCount?: number }) {
  const upload = useStagedUpload();
  const input = useRef<HTMLInputElement>(null);
  const headingId = useId();
  const summaryId = useId();
  const retry = retryCount !== undefined;
  const ready = upload.files.length - upload.invalid;
  return (
    <section aria-labelledby={headingId} id="upload" className="surface rounded-3xl p-5 sm:p-6">
      <div className="flex items-start gap-3">
        <span className="grid size-10 shrink-0 place-items-center rounded-full bg-white/80 text-ink ring-1 ring-ink/[0.06]">
          <FileUp className="size-5" aria-hidden="true" />
        </span>
        <div className="min-w-0">
          <h2 id={headingId} className="text-lg font-semibold">
            {retry ? "Select the original files again" : "Upload saved emails"}
          </h2>
          <p className="mt-1 text-sm leading-relaxed text-ink-soft">
            {retry
              ? `Uploaded emails aren't stored, so retrying ${retryCount === 1 ? "the email" : `the ${retryCount} emails`} that couldn't be read needs the same .eml files. Emails that already imported are skipped, never duplicated.`
              : `Import .eml files without connecting an account — up to ${UPLOAD_LIMITS.files} files, 2 MB each. Files are read in memory and never stored.`}
          </p>
        </div>
      </div>

      <details className="mt-4 rounded-2xl bg-well px-4 py-3 text-sm ring-1 ring-ink/5">
        <summary className="cursor-pointer font-semibold text-ink">
          How do I save an email as .eml?
        </summary>
        <ul className="mt-2 list-disc space-y-1 pl-5 leading-relaxed text-ink-soft">
          <li>Gmail on the web: open the email → More (⋮) → Download message.</li>
          <li>Outlook: open the email → File → Save As → choose the .eml or Outlook message format.</li>
          <li>Apple Mail: select the email → File → Save As → Raw Message Source, ending in .eml.</li>
        </ul>
        <p className="mt-2 leading-relaxed text-ink-soft">
          An .eml file is the original email, including the sender details FinBoy uses to check
          where a payment notice came from. Screenshots and PDFs can&apos;t be read.
        </p>
      </details>

      <input
        ref={input}
        type="file"
        multiple
        accept=".eml,message/rfc822"
        hidden
        onChange={(event) => {
          if (event.target.files) upload.add(event.target.files);
          event.target.value = "";
        }}
      />
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <Button
          type="button"
          variant="outline"
          disabled={upload.uploading}
          onClick={() => input.current?.click()}
        >
          <Mail aria-hidden="true" /> {upload.files.length ? "Add more files" : "Choose .eml files"}
        </Button>
        {upload.files.length > 0 && !upload.uploading && (
          <Button type="button" variant="ghost" onClick={upload.clear}>
            Clear selection
          </Button>
        )}
      </div>

      {upload.files.length > 0 && (
        <>
          <ul aria-label="Selected files" className="mt-4 divide-y rounded-2xl border">
            {upload.files.map((item) => (
              <li key={item.key} className="flex items-center gap-3 px-3 py-2 sm:px-4">
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{item.file.name}</p>
                  <p
                    className={cn(
                      "text-xs",
                      item.problem ? "font-semibold text-destructive" : "text-ink-soft",
                    )}
                  >
                    {item.problem ? problemCopy[item.problem] : formatBytes(item.file.size)}
                  </p>
                </div>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  disabled={upload.uploading}
                  aria-label={`Remove ${item.file.name}`}
                  onClick={() => upload.remove(item.key)}
                >
                  <X aria-hidden="true" />
                </Button>
              </li>
            ))}
          </ul>
          <p id={summaryId} role="status" className="mt-3 text-sm text-ink-soft">
            {`${upload.files.length} ${upload.files.length === 1 ? "file" : "files"} selected · ${formatBytes(upload.totalBytes)}`}
            {upload.invalid > 0 &&
              ` · ${upload.invalid} can't be imported — remove ${upload.invalid === 1 ? "it" : "them"} to continue`}
            {upload.tooMany && ` · choose at most ${UPLOAD_LIMITS.files} files`}
          </p>
        </>
      )}

      {upload.uploading ? (
        <div className="mt-4 space-y-2">
          <div className="flex items-center justify-between gap-3 text-sm font-medium">
            <span role="status">
              Uploading… {Math.round((upload.progress ?? 0) * 100)}%
            </span>
            <Button type="button" variant="ghost" size="sm" onClick={upload.cancel}>
              Cancel upload
            </Button>
          </div>
          <Progress
            value={Math.round((upload.progress ?? 0) * 100)}
            aria-label="Upload progress"
            className="h-1.5"
          />
        </div>
      ) : (
        upload.files.length > 0 && (
          <Button
            type="button"
            className="mt-4"
            aria-describedby={summaryId}
            disabled={!ready || upload.invalid > 0 || upload.tooMany}
            onClick={() => void upload.submit()}
          >
            {retry ? "Retry with these files" : `Import ${ready} ${ready === 1 ? "email" : "emails"}`}
          </Button>
        )
      )}
      {upload.problem && <ProblemNotice className="mt-4" problem={upload.problem} />}
    </section>
  );
}
