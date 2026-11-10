export type Segment = { text: string; bold: boolean };

// WhatsApp-style *bold*, which the advisor writes for both channels: asterisks around text that
// starts and ends with a non-space character and is not inside a word or number ("2*3*4").
const BOLD = /\*(?=\S)([^*\n]*?\S)\*(?![\p{L}\p{N}])/gu;
const WORD = /[\p{L}\p{N}]/u;

/** The text split into plain and bold runs, without the asterisks that mark bold. */
export function boldSegments(text: string): Segment[] {
  const segments: Segment[] = [];
  let last = 0;
  for (const match of text.matchAll(BOLD)) {
    const start = match.index;
    if (start > 0 && WORD.test(text[start - 1] ?? "")) continue;
    if (start > last) segments.push({ text: text.slice(last, start), bold: false });
    segments.push({ text: match[1] ?? "", bold: true });
    last = start + match[0].length;
  }
  if (last < text.length) segments.push({ text: text.slice(last), bold: false });
  return segments;
}
