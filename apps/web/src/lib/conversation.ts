import type { Answer, DisplayStyle } from "./api/assistant.ts";
import type { Problem } from "./messages.ts";

// Session-only question/answer pairs. They live in memory so leaving for an evidence record and
// pressing Back restores them; nothing is written to browser storage and a reload clears them.
export type Turn = {
  id: string;
  question: string;
  style: DisplayStyle;
  askedAt: number;
  state: "pending" | "answered" | "failed" | "cancelled";
  answer: Answer | null;
  problem: Problem | null;
};

let turns: Turn[] = [];
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
  emit();
}
