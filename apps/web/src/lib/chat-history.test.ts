import assert from "node:assert/strict";
import { test } from "node:test";
import { historyTurns } from "./chat-history.ts";

const THREAD = "3f2a6a5e-6f7b-4d43-9a3b-2b8f0f4c9d10";
const message = (id: number, role: "user" | "assistant", text: string, language: "en" | "hi" | "ml" = "en") => ({
  id: `00000000-0000-4000-8000-${String(id).padStart(12, "0")}`,
  role,
  text,
  language,
  created_at: `2026-11-07T04:3${id}:00Z`,
  change_set: null,
});

test("a saved chat becomes turns, newest first, in the script it was written in", () => {
  const turns = historyTurns(
    [
      message(1, "user", "Food?"),
      message(2, "assistant", "₹4,200 on food."),
      message(3, "user", "पिछले महीने?", "hi"),
      message(4, "assistant", "पिछले महीने ₹3,000।", "hi"),
      message(5, "user", "Aur is hafte?", "hi"),
      message(6, "assistant", "Is hafte ₹420.", "hi"),
    ],
    THREAD,
  );
  assert.deepEqual(
    turns.map((turn) => turn.question),
    ["Aur is hafte?", "पिछले महीने?", "Food?"],
  );
  assert.equal(turns[1]?.answer?.display_script, "Deva");
  assert.equal(turns[0]?.answer?.display_script, "Latn");
  assert.equal(turns[0]?.answer?.display_language, "hi");
  // Earlier answers are shown, not spoken: speech needs a fresh answer.
  assert.equal(turns[0]?.answer?.speech_text, "");
  assert.equal(turns[0]?.answer?.thread_id, THREAD);
});

test("a question without a saved answer is shown as not answered", () => {
  const turns = historyTurns([message(1, "user", "Food?")], THREAD);
  assert.equal(turns[0]?.state, "failed");
  assert.equal(turns[0]?.answer, null);
});

test("a message FinBoy sent first is shown as its own, without a question", () => {
  const turns = historyTurns(
    [
      message(1, "assistant", "🟡 Food & dining: ₹4,200 of your ₹5,000 budget spent."),
      message(2, "user", "How do I cut back?"),
      message(3, "assistant", "Cook at home twice this week."),
    ],
    THREAD,
  );
  assert.deepEqual(
    turns.map((turn) => [turn.question, turn.answer?.display_text]),
    [
      ["How do I cut back?", "Cook at home twice this week."],
      ["", "🟡 Food & dining: ₹4,200 of your ₹5,000 budget spent."],
    ],
  );
  assert.equal(turns[1]?.state, "answered");
});

test("an answer that proposed changes keeps them, with their state, when the chat reopens", () => {
  const changeSet = {
    id: "9b2f4c1e-5d6a-4e7b-8c9d-0e1f2a3b4c5d",
    state: "applied" as const,
    count: 2,
    groups: [
      {
        kind: "category" as const,
        category: "travel",
        names: ["REDBUS", "Indian Railways"],
        more_names: 0,
        new_name: null,
        payments: 2,
        amount_minor: 178220,
        before_minor: null,
        after_minor: null,
      },
    ],
    kept: 0,
    remembered: 2,
    skipped: 0,
    expires_at: "2026-11-08T04:32:00Z",
    applied_at: "2026-11-07T04:33:00Z",
    undone_at: null,
    data_version: null,
  };
  const [turn] = historyTurns(
    [message(1, "user", "Sort my Other payments"), { ...message(2, "assistant", "Two can move to travel."), change_set: changeSet }],
    THREAD,
  );
  assert.equal(turn?.answer?.change_set?.state, "applied");
  assert.equal(turn?.answer?.change_set?.groups[0]?.amount_minor, 178220);
});
