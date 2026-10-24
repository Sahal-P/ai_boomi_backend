// Unsaved record corrections, kept in memory per record so Back/Forward or a closed panel
// doesn't silently lose them. Never written to browser storage; cleared on save or discard.
export type CorrectionDraft = {
  merchant: string;
  amount: string;
  category: string;
  date: string;
  direction: "in" | "out";
  kind: string;
};

const drafts = new Map<string, CorrectionDraft>();

export function readDraft(id: string): CorrectionDraft | undefined {
  return drafts.get(id);
}

export function writeDraft(id: string, draft: CorrectionDraft | null) {
  if (draft) drafts.set(id, draft);
  else drafts.delete(id);
}
