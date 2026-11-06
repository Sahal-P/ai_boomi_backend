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
