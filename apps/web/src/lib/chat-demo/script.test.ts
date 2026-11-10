import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { test } from "node:test";
import {
  CATEGORY,
  CLIPS,
  SPENDING_ORDER,
  TEXT,
  categoryChanged,
  clock,
  deliver,
  fixTitle,
  initialChat,
  parseAmount,
  removed,
  removedMany,
  saved,
  savedMany,
  spokenSaved,
  tap,
  type ChatState,
  type Message,
  type Tap,
} from "./script.ts";

// Rebuilt from english.py by the API's tests/whatsapp/test_landing_chat.py.
const copy = JSON.parse(readFileSync(new URL("./finboy-copy.json", import.meta.url), "utf8")) as {
  texts: Record<string, string>;
  categories: Record<string, string>;
  spending_order: string[];
  examples: Record<string, string>;
};
const example = (name: string) => {
  const text = copy.examples[name];
  assert.ok(text, name);
  return text;
};

const groceries = (spent: number) => ({ category: "groceries" as const, limit: 600_000, spent });
const milkman = (amount: number, category: keyof typeof CATEGORY = "groceries") => ({ amount, category, payee: "milkman" });

/** Taps, then shows FinBoy's replies, as the page does after "typing…". */
function step(state: ChatState, input: Tap): { state: ChatState; replies: readonly Message[] } {
  const turn = tap(state, input);
  assert.ok(turn, `the tap ${JSON.stringify(input)} was refused`);
  return { state: deliver(turn.sent, turn.replies), replies: turn.replies };
}
const text = (message: Message | undefined) => (message && message.kind !== "voice" ? message.text : undefined);

test("the ports say exactly what FinBoy sends", () => {
  assert.deepEqual({ ...TEXT }, copy.texts);
  assert.deepEqual({ ...CATEGORY }, copy.categories);
  assert.deepEqual([...SPENDING_ORDER], copy.spending_order);
  const items = [
    { amount: 2_000, category: "food_dining" as const, payee: null },
    { amount: 5_000, category: "transport" as const, payee: null },
    { amount: 12_000, category: "food_dining" as const, payee: null },
  ];
  assert.equal(savedMany(items), example("saved_many"));
  assert.equal(saved(milkman(50_000), groceries(230_000)), example("saved_milkman"));
  assert.equal(spokenSaved(milkman(50_000)), example("spoken_milkman"));
  assert.equal(saved(milkman(40_000), groceries(220_000)), example("saved_milkman_400"));
  assert.equal(saved(milkman(300_000), groceries(480_000)), example("saved_milkman_near"));
  assert.equal(saved(milkman(500_000), groceries(680_000)), example("saved_milkman_over"));
  assert.equal(saved(milkman(45_050), groceries(225_050)), example("saved_milkman_paise"));
  assert.equal(saved(milkman(50_000, "food_dining"), null), example("saved_milkman_food"));
  assert.equal(saved({ amount: 5_000, category: "transport", payee: null }, null), example("saved_auto"));
  assert.equal(removed(milkman(50_000)), example("removed_milkman"));
  assert.equal(removed({ amount: 5_000, category: "transport", payee: null }), example("removed_auto"));
  assert.equal(removed({ amount: 12_345_600, category: "other", payee: null }), example("lakh"));
  assert.equal(removedMany(3, 19_000), example("removed_many_3"));
  assert.equal(removedMany(1, 2_000), example("removed_many_1"));
  assert.equal(categoryChanged("food_dining", "milkman"), example("category_changed_milkman"));
  assert.equal(categoryChanged("shopping", null), example("category_changed_auto"));
  assert.equal(fixTitle(2_000, CATEGORY.food_dining), example("fix_title_chai"));
  assert.equal(fixTitle(5_000, CATEGORY.transport), example("fix_title_auto"));
});

test("the opening chat is FinBoy's two cards and its spoken reply", () => {
  const { messages } = initialChat();
  assert.equal(text(messages[1]), example("saved_many"));
  assert.equal(text(messages[3]), example("saved_milkman"));
  assert.equal(CLIPS.finboy.words, example("spoken_milkman"));
  assert.deepEqual(
    messages.map((message) => [message.kind, message.time]),
    [["sent", "8:02 pm"], ["reply", "8:02 pm"], ["voice", "8:05 pm"], ["reply", "8:05 pm"], ["voice", "8:05 pm"]],
  );
});

test("Undo all takes the three out, quoting the card; then Fix one has nothing left", () => {
  const start = initialChat();
  const turn = tap(start, { kind: "button", message: 2, index: 0 });
  assert.ok(turn);
  assert.deepEqual(turn.sent.messages.at(-1), {
    id: 6,
    kind: "sent",
    time: "8:06 pm",
    text: TEXT.UNDO_ALL,
    quote: example("saved_many"),
  });
  assert.deepEqual(turn.replies.map(text), [example("removed_many_3")]);
  assert.equal(turn.replies[0]?.time, "8:06 pm");
  const after = deliver(turn.sent, turn.replies);
  assert.equal(tap(after, { kind: "button", message: 2, index: 0 }), null, "a tapped button is spent");
  const fix = step(after, { kind: "button", message: 2, index: 1 });
  assert.equal(text(fix.replies[0]), TEXT.NOTHING_TO_FIX);
  assert.equal(fix.state.messages.at(-1)?.time, "8:07 pm");
});

test("Fix one lists the three; a pick sends that entry's own card", () => {
  const listed = step(initialChat(), { kind: "button", message: 2, index: 1 });
  const list = listed.replies[0];
  assert.ok(list?.kind === "reply" && list.listing);
  assert.equal(list.text, TEXT.FIX_ASK);
  assert.deepEqual(
    list.listing.rows.map((row) => row.title),
    [example("fix_title_chai"), example("fix_title_auto"), "₹120 · Food & dining"],
  );
  const picked = step(listed.state, { kind: "row", message: list.id, index: 1 });
  assert.deepEqual(picked.state.messages.at(-2), {
    id: list.id + 1,
    kind: "sent",
    time: "8:07 pm",
    text: example("fix_title_auto"),
    quote: TEXT.FIX_ASK,
  });
  const card = picked.replies[0];
  assert.ok(card?.kind === "reply");
  assert.equal(card.text, example("saved_auto"));
  assert.deepEqual(card.buttons?.map((button) => button.label), [TEXT.UNDO, TEXT.AMOUNT, TEXT.CATEGORY_BUTTON]);
  assert.equal(tap(picked.state, { kind: "row", message: list.id, index: 0 }), null, "a list is used once");
});

test("Undo offers Put it back, which saves the card again; the old card then works again", () => {
  const undone = step(initialChat(), { kind: "button", message: 4, index: 0 });
  const removedCard = undone.replies[0];
  assert.ok(removedCard?.kind === "reply");
  assert.equal(removedCard.text, example("removed_milkman"));
  assert.deepEqual(removedCard.buttons?.map((button) => button.label), [TEXT.PUT_BACK]);
  const stale = step(undone.state, { kind: "button", message: 4, index: 1 });
  assert.equal(text(stale.replies[0]), TEXT.CHANGED, "Amount on a removed entry");
  const back = step(undone.state, { kind: "button", message: removedCard.id, index: 0 });
  assert.equal(text(back.replies[0]), `${TEXT.PUT_BACK_DONE}\n\n${example("saved_milkman")}`);
  const amount = step(back.state, { kind: "button", message: 4, index: 1 });
  assert.equal(text(amount.replies[0]), TEXT.CHANGE_ASK, "the entry is as the old card showed it");
});

test("Put it back on an entry that changed since is refused, as FinBoy refuses it", () => {
  const undone = step(initialChat(), { kind: "button", message: 4, index: 0 });
  const removedCard = undone.replies[0];
  assert.ok(removedCard?.kind === "reply");
  // No tap can change a removed entry in the demo, so the change is made directly.
  const { entries } = undone.state;
  const changed = { ...undone.state, entries: { ...entries, milkman: { ...entries.milkman, amount: 40_000 } } };
  const refused = step(changed, { kind: "button", message: removedCard.id, index: 0 });
  assert.equal(text(refused.replies[0]), TEXT.UNDO_REFUSED);
});

test("Amount: the reply recomputes the budget line; an unclear reply asks again", () => {
  const asked = step(initialChat(), { kind: "button", message: 4, index: 1 });
  assert.equal(text(asked.replies[0]), TEXT.CHANGE_ASK);
  assert.ok(asked.state.awaiting);
  assert.equal(tap(initialChat(), { kind: "amount", text: "400" }), null, "nothing is asked yet");
  const unclear = step(asked.state, { kind: "amount", text: "0" });
  assert.equal(text(unclear.replies[0]), TEXT.AMOUNT_UNCLEAR);
  assert.ok(unclear.state.awaiting, "FinBoy keeps waiting for the amount");
  const changed = step(unclear.state, { kind: "amount", text: "400" });
  assert.deepEqual(changed.state.messages.at(-2), {
    id: unclear.state.nextId,
    kind: "sent",
    time: "8:08 pm",
    text: "400",
  });
  assert.equal(text(changed.replies[0]), `${TEXT.AMOUNT_CHANGED}\n\n${example("saved_milkman_400")}`);
  assert.equal(changed.state.awaiting, null);
  const stale = step(changed.state, { kind: "button", message: 4, index: 2 });
  assert.equal(text(stale.replies[0]), TEXT.CHANGED, "the old card showed ₹500");
  for (const [typed, name] of [["3,000", "saved_milkman_near"], ["₹5000", "saved_milkman_over"], ["450.50", "saved_milkman_paise"]] as const) {
    const again = step(step(initialChat(), { kind: "button", message: 4, index: 1 }).state, { kind: "amount", text: typed });
    assert.equal(text(again.replies[0]), `${TEXT.AMOUNT_CHANGED}\n\n${example(name)}`, typed);
  }
});

test("Category lists FinBoy's ten and moves the milkman, remembering the payee", () => {
  const listed = step(initialChat(), { kind: "button", message: 4, index: 2 });
  const list = listed.replies[0];
  assert.ok(list?.kind === "reply" && list.listing);
  assert.equal(list.text, TEXT.CATEGORY_ASK);
  assert.equal(list.listing.open, TEXT.CATEGORY_OPEN);
  assert.equal(list.listing.section, TEXT.CATEGORY_SECTION);
  assert.deepEqual(
    list.listing.rows.map((row) => row.title),
    ["Food & dining", "Transport", "Shopping", "Power, water, gas", "Phone recharge", "Health", "Rent", "Education", "Family events", "Other"],
  );
  const moved = step(listed.state, { kind: "row", message: list.id, index: 0 });
  assert.equal(text(moved.replies[0]), `${example("category_changed_milkman")}\n\n${example("saved_milkman_food")}`);
});

test("times move on a minute per tap", () => {
  assert.equal(clock(2), "8:02 pm");
  assert.equal(clock(59), "8:59 pm");
  assert.equal(clock(60), "9:00 pm");
  const first = step(initialChat(), { kind: "button", message: 4, index: 1 });
  const second = step(first.state, { kind: "amount", text: "400" });
  assert.deepEqual([first.replies[0]?.time, second.replies[0]?.time], ["8:06 pm", "8:07 pm"]);
});

test("an amount is exactly one number, as FinBoy reads the reply to Amount", () => {
  assert.equal(parseAmount("400"), 40_000);
  assert.equal(parseAmount(" ₹ 1,23,456 "), 12_345_600);
  assert.equal(parseAmount("450.5"), 45_050);
  for (const bad of ["", "0", "1.234", "4 00", "12,34", "10000001"]) assert.equal(parseAmount(bad), null, bad);
});
