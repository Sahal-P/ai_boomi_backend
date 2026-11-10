import type { Answer, ChatMessage } from "./api/assistant.ts";
import type { Turn } from "./conversation.ts";

/** The script an earlier answer was written in, so it is announced in the right language. */
function scriptOf(text: string): Answer["display_script"] {
  if (/[ऀ-ॿ]/.test(text)) return "Deva";
  if (/[ഀ-ൿ]/.test(text)) return "Mlym";
  return "Latn";
}

/** An earlier answer as the turn card shows it: its words only, without speech or evidence. */
export function historyAnswer(text: string, language: ChatMessage["language"], threadId: string): Answer {
  const lang = language ?? "en";
  return {
    intent: "advisor",
    policy: "answer",
    display_text: text,
    speech_text: "",
    speech_language: lang,
    display_language: lang,
    display_script: scriptOf(text),
    facts: [],
    simulation: null,
    evidence_transactions: [],
    evidence_total: 0,
    evidence_sampled: false,
    warnings: [],
    warning_labels: {},
    data_version: "history",
    dataset: "household",
    resolved_period: null,
    thread_id: threadId,
    memory_changes: [],
    follow_ups: [],
    sources: [],
  };
}

/**
 * A saved chat (oldest first, question then answer) as turns, newest first like the store. A
 * message FinBoy sent first (a coach nudge on WhatsApp, advisor phase 3) is a turn without a
 * question.
 */
export function historyTurns(messages: ChatMessage[], threadId: string): Turn[] {
  const turns: Turn[] = [];
  for (let index = 0; index < messages.length; index += 1) {
    const question = messages[index];
    const reply = messages[index + 1];
    if (!question) continue;
    if (question.role === "assistant") {
      turns.push({
        id: `history-${question.id}`,
        question: "",
        style: "auto",
        askedAt: Date.parse(question.created_at),
        state: "answered",
        answer: historyAnswer(question.text, question.language, threadId),
        problem: null,
      });
      continue;
    }
    const answered = reply?.role === "assistant";
    turns.push({
      id: `history-${question.id}`,
      question: question.text,
      style: "auto",
      askedAt: Date.parse(question.created_at),
      state: answered ? "answered" : "failed",
      answer: answered ? historyAnswer(reply.text, reply.language, threadId) : null,
      problem: answered
        ? null
        : { title: "No answer was saved", detail: "Ask it again.", reference: null, kind: "unknown", code: null },
    });
    if (answered) index += 1;
  }
  return turns.reverse();
}
