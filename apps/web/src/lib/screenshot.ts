import { SCREENSHOT_LIMIT, type Screenshot } from "./api/feedback.ts";

// A screenshot is redrawn on a canvas before it is sent (docs/feedback-round/contract.md): the copy
// carries no location, camera or other file details, and fits under the API's 1.5 MB limit.
export const SCREENSHOT_ACCEPT = "image/png,image/jpeg,image/webp";
const ACCEPTED = new Set(SCREENSHOT_ACCEPT.split(","));
/** A picked file larger than this isn't opened at all. */
export const SCREENSHOT_SOURCE_LIMIT = 25 * 1024 * 1024;
const MAX_WIDTH = 1600;
const MAX_HEIGHT = 4000;
const QUALITIES = [0.85, 0.7, 0.55, 0.4];

export type ScreenshotReason = "type" | "size" | "unreadable";
export class ScreenshotProblem extends Error {
  readonly reason: ScreenshotReason;
  constructor(reason: ScreenshotReason) {
    super(`The screenshot can't be attached (${reason}).`);
    this.name = "ScreenshotProblem";
    this.reason = reason;
  }
}

export const acceptsScreenshot = (type: string) => ACCEPTED.has(type);

/** The redrawn size: at most 1,600 px wide and 4,000 px tall, never larger than the original. */
export function fitted(width: number, height: number): { width: number; height: number } {
  const scale = Math.min(1, MAX_WIDTH / width, MAX_HEIGHT / height);
  return { width: Math.max(1, Math.round(width * scale)), height: Math.max(1, Math.round(height * scale)) };
}

/** The base64 part of a data: URL. */
export function base64Of(dataUrl: string): string {
  const comma = dataUrl.indexOf(",");
  return comma === -1 ? "" : dataUrl.slice(comma + 1);
}

const encoded = (canvas: HTMLCanvasElement, type: string, quality: number) =>
  new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, type, quality));

const dataUrlOf = (blob: Blob) =>
  new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(typeof reader.result === "string" ? reader.result : "");
    reader.onerror = () => reject(new ScreenshotProblem("unreadable"));
    reader.readAsDataURL(blob);
  });

/** Redraws a picked picture as WebP (JPEG where the browser can't write WebP) under the limit. */
export async function redraw(file: File): Promise<{ blob: Blob; screenshot: Screenshot }> {
  if (!acceptsScreenshot(file.type)) throw new ScreenshotProblem("type");
  if (file.size > SCREENSHOT_SOURCE_LIMIT) throw new ScreenshotProblem("size");
  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(file);
  } catch {
    throw new ScreenshotProblem("unreadable");
  }
  try {
    const size = fitted(bitmap.width, bitmap.height);
    const canvas = document.createElement("canvas");
    canvas.width = size.width;
    canvas.height = size.height;
    const context = canvas.getContext("2d");
    if (!context) throw new ScreenshotProblem("unreadable");
    // JPEG has no transparency: transparent parts become white rather than black.
    context.fillStyle = "#ffffff";
    context.fillRect(0, 0, size.width, size.height);
    context.drawImage(bitmap, 0, 0, size.width, size.height);
    for (const type of ["image/webp", "image/jpeg"] as const) {
      for (const quality of QUALITIES) {
        const blob = await encoded(canvas, type, quality);
        if (!blob || blob.type !== type) break; // this browser can't write this type
        if (blob.size <= SCREENSHOT_LIMIT) {
          return { blob, screenshot: { type, data: base64Of(await dataUrlOf(blob)) } };
        }
      }
    }
    throw new ScreenshotProblem("size");
  } finally {
    bitmap.close();
  }
}
