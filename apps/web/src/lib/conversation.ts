import type { Answer, DisplayStyle } from "./api/assistant.ts";
import type { Problem } from "./messages.ts";

// Question/answer pairs for the chat on screen. They live in memory so leaving for an evidence
// record and pressing Back restores them; nothing is written to browser storage. With the advisor
// on, the server keeps the chat itself (`threadId`), so it can be reopened from Recent chats.
export type Turn = {
  id: string;
  question: string;
  style: DisplayStyle;
  askedAt: number;
  state: "pending" | "answered" | "failed" | "cancelled";
  answer: Answer | null;
  problem: Problem | null;
  /** The advisor's current step while it works, streamed from the API (advisor phase 2). */
  progress?: string | null;
};

let turns: Turn[] = [];
let thread: string | null = null;
const listeners = new Set<() => void>();
let counter = 0;

function emit() {
  for (const listener of [...listeners]) listener();
}

export function subscribeTurns(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export const getTurns = () => turns;
/** The server chat these turns belong to; null until the first answer of a new chat. */
export const getThreadId = () => thread;

export function setThreadId(id: string | null) {
  thread = id;
}
const empty: Turn[] = [];
export const getServerTurns = () => empty;

export function addTurn(question: string, style: DisplayStyle): string {
  counter += 1;
  const id = `turn-${counter}`;
  const turn: Turn = { id, question, style, askedAt: Date.now(), state: "pending", answer: null, problem: null };
  turns = [turn, ...turns].slice(0, 20);
  emit();
  return id;
}

export function updateTurn(id: string, change: Partial<Omit<Turn, "id">>) {
  turns = turns.map((turn) => (turn.id === id ? { ...turn, ...change } : turn));
  emit();
}

export function clearTurns() {
  turns = [];
  thread = null;
  emit();
}

/** Shows an earlier chat: its turns newest first, continuing it with the next question. */
export function replaceTurns(next: Turn[], threadId: string) {
  turns = next.slice(0, 40);
  thread = threadId;
  emit();
}
