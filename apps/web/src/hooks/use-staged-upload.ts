"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { isAbort } from "@/lib/api/http";
import { fileProblem, UPLOAD_LIMITS, uploadEml, type FileProblem } from "@/lib/api/imports";
import { describeProblem, type Problem } from "@/lib/messages";

export type StagedFile = { key: string; file: File; problem: FileProblem | null };

const fileKey = (file: File) => `${file.name}:${file.size}:${file.lastModified}`;

/**
 * Files are staged and validated locally; nothing is sent until Import is pressed.
 * Selections live only in memory for this page.
 */
export function useStagedUpload() {
  const router = useRouter();
  const [files, setFiles] = useState<StagedFile[]>([]);
  const [progress, setProgress] = useState<number | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const control = useRef<AbortController | null>(null);

  function add(list: FileList | File[]) {
    setProblem(null);
    setFiles((current) => {
      const seen = new Set(current.map((item) => item.key));
      const next = [...current];
      for (const file of Array.from(list)) {
        const key = fileKey(file);
        if (seen.has(key)) continue;
        seen.add(key);
        next.push({ key, file, problem: fileProblem(file) });
      }
      return next;
    });
  }

  const invalid = files.filter((item) => item.problem !== null).length;
  const tooMany = files.length > UPLOAD_LIMITS.files;
  const totalBytes = files.reduce((sum, item) => sum + item.file.size, 0);
  const uploading = progress !== null;

  async function submit() {
    if (!files.length || invalid || tooMany || uploading) return;
    const controller = new AbortController();
    control.current = controller;
    setProblem(null);
    setProgress(0);
    try {
      const started = await uploadEml(
        files.map((item) => item.file),
        { signal: controller.signal, onProgress: setProgress },
      );
      setFiles([]);
      router.push(`/import/${started.import_run_id}`);
    } catch (error) {
      setProblem(
        isAbort(error)
          ? {
              title: "Upload cancelled",
              detail: "Nothing was imported. Your selected files are still listed here.",
              reference: null,
              kind: "unknown",
              code: null,
            }
          : describeProblem(error, "Your emails weren't imported"),
      );
    } finally {
      control.current = null;
      setProgress(null);
    }
  }

  return {
    files,
    add,
    remove: (key: string) => setFiles((current) => current.filter((item) => item.key !== key)),
    clear: () => setFiles([]),
    invalid,
    tooMany,
    totalBytes,
    progress,
    uploading,
    problem,
    submit,
    cancel: () => control.current?.abort(),
  };
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
