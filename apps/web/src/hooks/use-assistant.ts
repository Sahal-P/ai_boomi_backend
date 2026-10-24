"use client";

import { useSyncExternalStore } from "react";
import { askQuestion, styles, type DisplayStyle } from "@/lib/api/assistant";
import { isAbort } from "@/lib/api/http";
import { addTurn, clearTurns, getServerTurns, getTurns, subscribeTurns, updateTurn } from "@/lib/conversation";
import { describeProblem } from "@/lib/messages";

// The request in flight is module-scoped so an answer still arrives if you open its evidence
// and come back; Cancel aborts it explicitly.
let inflight: { id: string; controller: AbortController } | null = null;
const STYLE_KEY = "finboy:reply-style";
const styleListeners = new Set<() => void>();

function readStyle(): DisplayStyle {
  try {
    const stored = window.sessionStorage.getItem(STYLE_KEY);
    return styles.find((style) => style === stored) ?? "auto";
  } catch {
    return "auto";
  }
}

/** Reply style is a display preference remembered for this browser session only. */
export function setReplyStyle(style: DisplayStyle) {
  try {
    window.sessionStorage.setItem(STYLE_KEY, style);
  } catch {
    // Storage unavailable: the choice still applies until the page reloads.
  }
  styleListeners.forEach((listener) => listener());
}

function subscribeStyle(listener: () => void) {
  styleListeners.add(listener);
  return () => {
    styleListeners.delete(listener);
  };
}

async function run(id: string, question: string, style: DisplayStyle) {
  inflight?.controller.abort();
  const controller = new AbortController();
  inflight = { id, controller };
  try {
    const answer = await askQuestion(question, style, controller.signal);
    updateTurn(id, { state: "answered", answer, problem: null });
  } catch (error) {
    if (isAbort(error) || controller.signal.aborted) updateTurn(id, { state: "cancelled" });
    else updateTurn(id, { state: "failed", problem: describeProblem(error, "FinBoy couldn't answer that") });
  } finally {
    if (inflight?.id === id) inflight = null;
  }
}

export function useAssistant() {
  const turns = useSyncExternalStore(subscribeTurns, getTurns, getServerTurns);
  const style = useSyncExternalStore(subscribeStyle, readStyle, () => "auto" as const);
  const pending = turns.some((turn) => turn.state === "pending");
  return {
    turns,
    pending,
    style,
    setStyle: setReplyStyle,
    ask(question: string, askStyle: DisplayStyle = style) {
      const text = question.trim().slice(0, 2000);
      if (!text || pending) return false;
      void run(addTurn(text, askStyle), text, askStyle);
      return true;
    },
    retry(id: string) {
      const turn = turns.find((item) => item.id === id);
      if (!turn || pending) return;
      updateTurn(id, { state: "pending", problem: null, askedAt: Date.now() });
      void run(id, turn.question, turn.style);
    },
    cancel() {
      inflight?.controller.abort();
    },
    clear() {
      inflight?.controller.abort();
      clearTurns();
    },
  };
}
