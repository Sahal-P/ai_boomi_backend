"use client";

import { ImagePlus, LoaderCircle, X } from "lucide-react";
import Image from "next/image";
import { useEffect, useId, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import type { Screenshot } from "@/lib/api/feedback";
import { redraw, SCREENSHOT_ACCEPT, ScreenshotProblem, type ScreenshotReason } from "@/lib/screenshot";

/** A picked screenshot and the private blob URL of its redrawn copy, for the preview. */
export type Attachment = { screenshot: Screenshot; preview: string; width: number; height: number };

const reasons: Record<ScreenshotReason, string> = {
  type: "That file can't be attached. Choose a PNG, JPEG or WebP screenshot.",
  size: "That picture is too large. Try a smaller screenshot.",
  unreadable: "That picture couldn't be opened. Try another screenshot.",
};

const sizeOf = (blob: Blob) =>
  createImageBitmap(blob).then((bitmap) => {
    const size = { width: bitmap.width, height: bitmap.height };
    bitmap.close();
    return size;
  });

/** One optional screenshot: redrawn on this device first, previewed, and removable. */
export function ScreenshotPicker({
  value,
  onChange,
  disabled,
}: {
  value: Attachment | null;
  onChange: (value: Attachment | null) => void;
  disabled: boolean;
}) {
  const ids = useId();
  const input = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  // The preview's blob URL is forgotten when it's replaced, removed or the page closes.
  const shown = useRef<string | null>(null);
  useEffect(() => {
    if (shown.current && shown.current !== value?.preview) URL.revokeObjectURL(shown.current);
    shown.current = value?.preview ?? null;
  }, [value]);
  useEffect(
    () => () => {
      if (shown.current) URL.revokeObjectURL(shown.current);
    },
    [],
  );

  async function pick(file: File | undefined) {
    if (!file) return;
    setBusy(true);
    setProblem(null);
    try {
      const { blob, screenshot } = await redraw(file);
      const size = await sizeOf(blob);
      onChange({ screenshot, preview: URL.createObjectURL(blob), ...size });
    } catch (reason) {
      setProblem(reasons[reason instanceof ScreenshotProblem ? reason.reason : "unreadable"]);
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  }

  return (
    <div className="space-y-2">
      <input
        ref={input}
        id={`${ids}-file`}
        type="file"
        accept={SCREENSHOT_ACCEPT}
        className="sr-only"
        tabIndex={-1}
        aria-hidden="true"
        onChange={(event) => void pick(event.target.files?.[0])}
      />
      {value ? (
        <div className="flex items-start gap-3">
          {/* A private blob URL, shown at its own shape and never sent to an image optimiser. */}
          <Image
            src={value.preview}
            alt="Your screenshot, as it will be sent"
            width={value.width}
            height={value.height}
            unoptimized
            className="h-auto max-h-48 w-auto max-w-[min(100%,12rem)] rounded-xl border border-ink/10 bg-white object-contain"
          />
          <Button type="button" variant="outline" size="sm" disabled={disabled} onClick={() => onChange(null)}>
            <X aria-hidden="true" /> Remove screenshot
          </Button>
        </div>
      ) : (
        <Button
          type="button"
          variant="outline"
          disabled={disabled || busy}
          aria-describedby={`${ids}-hint`}
          onClick={() => input.current?.click()}
        >
          {busy ? (
            <LoaderCircle aria-hidden="true" className="motion-safe:animate-spin" />
          ) : (
            <ImagePlus aria-hidden="true" />
          )}
          {busy ? "Preparing the screenshot…" : "Add a screenshot"}
        </Button>
      )}
      <p id={`${ids}-hint`} className="text-xs leading-relaxed text-ink-soft">
        Optional. It&apos;s redrawn on your device, so the location and camera details in the file are left out.
        The FinBoy team sees whatever it shows.
      </p>
      {problem && (
        <p role="alert" className="text-xs font-medium text-destructive">
          {problem}
        </p>
      )}
    </div>
  );
}
