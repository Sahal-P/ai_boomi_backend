/**
 * The landing chat's script: FinBoy's real WhatsApp replies (apps/api/src/finboy/services/whatsapp/
 * english.py), in the diary flows that send them (pilot.py), for a demo household that lives only
 * in the visitor's browser. Nothing is sent or stored.
 *
 * finboy-copy.json pins every text:
 * - script.test.ts checks these ports against it;
 * - the API's tests/whatsapp/test_landing_chat.py rebuilds it from english.py.
 * A wording change there therefore fails a test before the landing says something FinBoy doesn't.
 */

export const TEXT = {
  UNDO: "↩️ Undo",
  AMOUNT: "✏️ Amount",
  CATEGORY_BUTTON: "🏷️ Category",
  PUT_BACK: "↩️ Put it back",
  UNDO_ALL: "↩️ Undo all",
  FIX_ONE: "✏️ Fix one",
  CHANGE_ASK: "✏️ Say or type the right amount. Like: 400",
  AMOUNT_CHANGED: "✏️ Amount changed.",
  AMOUNT_UNCLEAR: "I didn't get the amount. Say or type just the amount, like: 400",
  PUT_BACK_DONE: "↩️ Put back.",
  FIX_ASK: "✏️ Which entry do you want to change?",
  FIX_OPEN: "Choose entry",
  FIX_SECTION: "Saved entries",
  CATEGORY_ASK: "🏷️ Which category? Pick one from the list, or type it, like: Groceries",
  CATEGORY_OPEN: "Choose category",
  CATEGORY_SECTION: "Categories",
  CHANGED: "This record has already changed. Send a new message.",
  UNDO_REFUSED: "This can't be undone now — something else changed after it.",
  NOTHING_TO_FIX: "These entries have already changed. Send a new message.",
} as const;

export const CATEGORY = {
  groceries: "Groceries",
  food_dining: "Food & dining",
  transport: "Transport",
  shopping: "Shopping",
  utilities: "Power, water, gas",
  phone_recharge: "Phone recharge",
  health: "Health",
  rent: "Rent",
  education: "Education",
  family_events: "Family events",
  other: "Other",
} as const;
export type Category = keyof typeof CATEGORY;

/**
 * The start of pilot.py's SPENDING_ORDER. The real list puts the household's own top spends first;
 * the demo household's (groceries, food, transport) already lead it.
 */
export const SPENDING_ORDER: readonly Category[] = [
  "groceries",
  "food_dining",
  "transport",
  "shopping",
  "utilities",
  "phone_recharge",
  "health",
  "rent",
  "education",
  "family_events",
];

function indianDigits(value: number): string {
  const digits = String(value);
  if (digits.length <= 3) return digits;
  const groups: string[] = [];
  for (let head = digits.slice(0, -3); head; head = head.slice(0, -2)) groups.unshift(head.slice(-2));
  return [...groups, digits.slice(-3)].join(",");
}

/** english.py's money(): ₹ with Indian grouping, paise only when there are any. */
export function money(minor: number): string {
  const whole = Math.floor(Math.abs(minor) / 100);
  const paise = Math.abs(minor) % 100;
  return `${minor < 0 ? "-" : ""}₹${indianDigits(whole)}${paise ? `.${String(paise).padStart(2, "0")}` : ""}`;
}

export interface Budget {
  readonly category: Category;
  readonly limit: number;
  readonly spent: number;
}

/** 🟢 under 80% of the limit, 🟡 from 80%, 🔴 once over it. */
export function budgetLine({ category, limit, spent }: Budget): string {
  const name = CATEGORY[category];
  if (spent > limit) return `🔴 ${name}: ${money(spent)} of ${money(limit)} — ${money(spent - limit)} over this month`;
  if (spent * 5 >= limit * 4) return `🟡 ${name}: ${money(spent)} of ${money(limit)} — ${money(limit - spent)} left this month`;
  return `🟢 ${name}: ${money(spent)} of ${money(limit)} this month`;
}

interface Item {
  readonly amount: number;
  readonly category: Category;
  readonly payee: string | null;
}

/** A saved entry, paid today (every demo entry is). */
export function saved(item: Item, budget: Budget | null): string {
  const lines = [`✅ Saved: ${money(item.amount)} paid`, `🏷️ ${CATEGORY[item.category]}`];
  if (item.payee) lines.push(`👤 ${item.payee}`);
  lines.push("📅 Today");
  if (budget) lines.push(budgetLine(budget));
  return lines.join("\n");
}

/** saved()'s spoken twin, as FinBoy says it after a voice note. */
export function spokenSaved(item: Item): string {
  const rupees = `${indianDigits(Math.floor(item.amount / 100))} rupees${item.amount % 100 ? ` ${item.amount % 100} paise` : ""}`;
  return `Saved, ${rupees} paid${item.payee ? `, ${item.payee}.` : "."}`;
}

export function savedMany(items: readonly Item[]): string {
  const total = items.reduce((sum, item) => sum + item.amount, 0);
  const lines = items.map(
    (item) => `• ${money(item.amount)} · ${CATEGORY[item.category]}${item.payee ? ` · ${item.payee}` : ""}`,
  );
  return [`✅ Saved ${items.length} · ${money(total)}`, ...lines].join("\n");
}

export const removed = (item: Item): string =>
  `↩️ Removed: ${money(item.amount)} paid${item.payee ? ` · ${item.payee}` : ""}`;

export const removedMany = (count: number, total: number): string =>
  `↩️ Removed ${count} ${count === 1 ? "entry" : "entries"} (${money(total)}).`;

export const categoryChanged = (category: Category, payee: string | null): string =>
  `🏷️ Changed to ${CATEGORY[category]}.${payee ? ` Next time, ${payee} goes there too.` : ""}`;

/** A list row title: WhatsApp allows 24 characters. */
export function fixTitle(amount: number, name: string): string {
  const title = [...`${money(amount)} · ${name}`];
  return title.length <= 24 ? title.join("") : `${title.slice(0, 23).join("")}…`;
}

// The demo household.

export type EntryId = "chai" | "auto" | "lunch" | "milkman";

export interface Entry extends Item {
  readonly id: EntryId;
  readonly saved: boolean;
}

/** What a card showed. Like pilot.py's record fingerprints, a tap acts only on that. */
const print = (entry: Entry) => `${entry.amount}|${entry.category}|${entry.saved}`;

const ENTRIES: Readonly<Record<EntryId, Entry>> = {
  chai: { id: "chai", amount: 2_000, category: "food_dining", payee: null, saved: true },
  auto: { id: "auto", amount: 5_000, category: "transport", payee: null, saved: true },
  lunch: { id: "lunch", amount: 12_000, category: "food_dining", payee: null, saved: true },
  milkman: { id: "milkman", amount: 50_000, category: "groceries", payee: "milkman", saved: true },
};

// The one budget: ₹6,000 on groceries, ₹1,800 spent elsewhere this month, so the milkman makes ₹2,300.
const GROCERIES_LIMIT = 600_000;
const GROCERIES_ELSEWHERE = 180_000;

function budgetFor(entries: Readonly<Record<EntryId, Entry>>, category: Category): Budget | null {
  if (category !== "groceries") return null;
  const spent = Object.values(entries)
    .filter((entry) => entry.saved && entry.category === "groceries")
    .reduce((sum, entry) => sum + entry.amount, GROCERIES_ELSEWHERE);
  return { category, limit: GROCERIES_LIMIT, spent };
}

/** pilot.py's _likely: ten categories, the current one left out and Other last. */
function likely(current: Category): Category[] {
  const choices = SPENDING_ORDER.filter((category) => category !== current).slice(0, 9);
  return current === "other" ? choices : [...choices, "other"];
}

export interface Snapshot {
  readonly entry: EntryId;
  readonly print: string;
}

export type Action =
  | { readonly kind: "undo_all"; readonly group: readonly Snapshot[] }
  | { readonly kind: "fix_one"; readonly group: readonly Snapshot[] }
  | ({ readonly kind: "undo" } & Snapshot)
  | ({ readonly kind: "amount" } & Snapshot)
  | ({ readonly kind: "category" } & Snapshot)
  | ({ readonly kind: "put_back" } & Snapshot);

export interface ReplyButton {
  readonly label: string;
  readonly action: Action;
}

export type Pick =
  | ({ readonly kind: "fix" } & Snapshot)
  | ({ readonly kind: "set_category"; readonly category: Category } & Snapshot);

export interface Listing {
  readonly open: string;
  readonly section: string;
  readonly rows: readonly { readonly title: string; readonly pick: Pick }[];
}

export interface Clip {
  readonly src: string;
  readonly seconds: number;
  /** Bar heights in px, measured from the clip's loudness (3–18). */
  readonly bars: readonly number[];
  readonly words: string;
}

/** AI voices: Sarvam Bulbul v3 for the visitor, FinBoy's own production voice for its reply. */
export const CLIPS = {
  you: {
    src: "/audio/chat-you.mp3",
    seconds: 2.11,
    bars: [3, 13, 18, 17, 11, 11, 14, 13, 14, 8, 4, 13, 14, 13, 8, 3, 3, 4, 12, 17, 13, 16, 14, 15, 6, 3, 3, 3],
    words: "Paid the milkman 500",
  },
  finboy: {
    src: "/audio/chat-finboy.mp3",
    seconds: 2.94,
    bars: [3, 3, 18, 17, 12, 5, 3, 16, 15, 16, 15, 12, 14, 8, 13, 6, 7, 17, 14, 10, 14, 11, 8, 9, 8, 7, 3, 3],
    words: spokenSaved(ENTRIES.milkman),
  },
} as const satisfies Record<string, Clip>;

export type Message =
  | { readonly id: number; readonly kind: "sent"; readonly time: string; readonly text: string; readonly quote?: string }
  | {
      readonly id: number;
      readonly kind: "reply";
      readonly time: string;
      readonly text: string;
      readonly buttons?: readonly ReplyButton[];
      readonly listing?: Listing;
    }
  | { readonly id: number; readonly kind: "voice"; readonly time: string; readonly from: "you" | "finboy"; readonly clip: keyof typeof CLIPS };

type Draft = Omit<Extract<Message, { kind: "reply" }>, "id" | "time">;

export interface ChatState {
  readonly entries: Readonly<Record<EntryId, Entry>>;
  readonly messages: readonly Message[];
  /** Tapped buttons (`message:index`) and used lists (`message:list`): WhatsApp greys them out. */
  readonly used: readonly string[];
  /** After ✏️ Amount, the next message is read as the amount (pilot.py's change_amount prompt). */
  readonly awaiting: Snapshot | null;
  /** The next message's minute after 8 pm: each tap moves the chat on a minute. */
  readonly minute: number;
  readonly nextId: number;
}

export type Tap =
  | { readonly kind: "button"; readonly message: number; readonly index: number }
  | { readonly kind: "row"; readonly message: number; readonly index: number }
  | { readonly kind: "amount"; readonly text: string };

/** Your message at once, and FinBoy's replies to show after "typing…". */
export interface Turn {
  readonly sent: ChatState;
  readonly replies: readonly Message[];
}

export function clock(minute: number): string {
  const hour = 8 + Math.floor(minute / 60);
  return `${hour > 12 ? hour - 12 : hour}:${String(minute % 60).padStart(2, "0")} pm`;
}

export const usedKey = (message: number, index: number | "list") => `${message}:${index}`;

function cardButtons(entry: Entry): ReplyButton[] {
  const snapshot = { entry: entry.id, print: print(entry) };
  return [
    { label: TEXT.UNDO, action: { kind: "undo", ...snapshot } },
    { label: TEXT.AMOUNT, action: { kind: "amount", ...snapshot } },
    { label: TEXT.CATEGORY_BUTTON, action: { kind: "category", ...snapshot } },
  ];
}

export function initialChat(): ChatState {
  const entries = ENTRIES;
  const group = (["chai", "auto", "lunch"] as const).map((id) => ({ entry: id, print: print(entries[id]) }));
  const milkman = entries.milkman;
  return {
    entries,
    messages: [
      { id: 1, kind: "sent", time: clock(2), text: "chai 20, auto 50, lunch 120" },
      {
        id: 2,
        kind: "reply",
        time: clock(2),
        text: savedMany([entries.chai, entries.auto, entries.lunch]),
        buttons: [
          { label: TEXT.UNDO_ALL, action: { kind: "undo_all", group } },
          { label: TEXT.FIX_ONE, action: { kind: "fix_one", group } },
        ],
      },
      { id: 3, kind: "voice", time: clock(5), from: "you", clip: "you" },
      {
        id: 4,
        kind: "reply",
        time: clock(5),
        text: saved(milkman, budgetFor(entries, milkman.category)),
        buttons: cardButtons(milkman),
      },
      { id: 5, kind: "voice", time: clock(5), from: "finboy", clip: "finboy" },
    ],
    used: [],
    awaiting: null,
    minute: 6,
    nextId: 6,
  };
}

/**
 * "Exactly one stated amount", as FinBoy reads the reply to ✏️ Amount. The field accepts only digits,
 * commas, a point and ₹, so number words never reach it.
 */
export function parseAmount(text: string): number | null {
  // Indian (1,23,456) or international (123,456) grouping, or none; at most two decimals.
  const found = text
    .trim()
    .replace(/^₹\s*/, "")
    .match(/^(\d{1,2}(?:,\d{2})*,\d{3}|\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d{1,2}))?$/);
  if (!found?.[1]) return null;
  const minor = Number(found[1].replace(/,/g, "")) * 100 + Number((found[2] ?? "").padEnd(2, "0"));
  return minor > 0 && minor <= 1_000_000_000 ? minor : null;
}

export function tap(state: ChatState, input: Tap): Turn | null {
  let entries = state.entries;
  let awaiting = state.awaiting;
  let used = state.used;
  const replies: Draft[] = [];
  let you: { text: string; quote?: string };

  const change = (id: EntryId, patch: Partial<Entry>) => {
    entries = { ...entries, [id]: { ...entries[id], ...patch } };
  };
  const fresh = (snapshot: Snapshot) => print(entries[snapshot.entry]) === snapshot.print;
  const card = (id: EntryId, prefix = ""): Draft => ({
    kind: "reply",
    text: prefix + saved(entries[id], budgetFor(entries, entries[id].category)),
    buttons: cardButtons(entries[id]),
  });
  const say = (text: string): Draft => ({ kind: "reply", text });

  if (input.kind === "amount") {
    if (!awaiting || !input.text.trim()) return null;
    you = { text: input.text.trim() };
    const amount = parseAmount(input.text);
    if (amount === null) replies.push(say(TEXT.AMOUNT_UNCLEAR));
    else if (!fresh(awaiting)) {
      replies.push(say(TEXT.CHANGED));
      awaiting = null;
    } else {
      const { entry } = awaiting;
      awaiting = null;
      change(entry, { amount });
      replies.push(card(entry, `${TEXT.AMOUNT_CHANGED}\n\n`));
    }
  } else {
    const message = state.messages.find((item) => item.id === input.message);
    if (message?.kind !== "reply") return null;
    if (input.kind === "row") {
      const row = message.listing?.rows[input.index];
      const key = usedKey(message.id, "list");
      if (!row || used.includes(key)) return null;
      you = { text: row.title, quote: message.text };
      used = [...used, key];
      const { pick } = row;
      if (!fresh(pick)) replies.push(say(TEXT.CHANGED));
      else if (pick.kind === "fix") replies.push(card(pick.entry));
      else {
        change(pick.entry, { category: pick.category });
        replies.push(card(pick.entry, `${categoryChanged(pick.category, entries[pick.entry].payee)}\n\n`));
      }
    } else {
      const button = message.buttons?.[input.index];
      const key = usedKey(message.id, input.index);
      if (!button || used.includes(key)) return null;
      you = { text: button.label, quote: message.text };
      used = [...used, key];
      const { action } = button;
      if (action.kind === "undo_all") {
        let count = 0;
        let total = 0;
        for (const snapshot of action.group) {
          if (!entries[snapshot.entry].saved || !fresh(snapshot)) continue;
          count += 1;
          total += entries[snapshot.entry].amount;
          change(snapshot.entry, { saved: false });
        }
        replies.push(say(count ? removedMany(count, total) : TEXT.NOTHING_TO_FIX));
      } else if (action.kind === "fix_one") {
        const rows = action.group
          .map((snapshot) => entries[snapshot.entry])
          .filter((entry) => entry.saved)
          .map((entry) => ({
            title: fixTitle(entry.amount, entry.payee ?? CATEGORY[entry.category]),
            pick: { kind: "fix" as const, entry: entry.id, print: print(entry) },
          }));
        replies.push(
          rows.length
            ? { kind: "reply", text: TEXT.FIX_ASK, listing: { open: TEXT.FIX_OPEN, section: TEXT.FIX_SECTION, rows } }
            : say(TEXT.NOTHING_TO_FIX),
        );
      } else if (action.kind === "put_back") {
        if (!fresh(action) || entries[action.entry].saved) replies.push(say(TEXT.UNDO_REFUSED));
        else {
          change(action.entry, { saved: true });
          replies.push(card(action.entry, `${TEXT.PUT_BACK_DONE}\n\n`));
        }
      } else if (!fresh(action)) {
        replies.push(say(TEXT.CHANGED));
      } else if (action.kind === "undo") {
        const entry = entries[action.entry];
        change(entry.id, { saved: false });
        const back = { entry: entry.id, print: print(entries[entry.id]) };
        replies.push({ kind: "reply", text: removed(entry), buttons: [{ label: TEXT.PUT_BACK, action: { kind: "put_back", ...back } }] });
      } else if (action.kind === "amount") {
        awaiting = { entry: action.entry, print: action.print };
        replies.push(say(TEXT.CHANGE_ASK));
      } else {
        const entry = entries[action.entry];
        const rows = likely(entry.category).map((category) => ({
          title: CATEGORY[category],
          pick: { kind: "set_category" as const, category, entry: entry.id, print: print(entry) },
        }));
        replies.push({
          kind: "reply",
          text: TEXT.CATEGORY_ASK,
          listing: { open: TEXT.CATEGORY_OPEN, section: TEXT.CATEGORY_SECTION, rows },
        });
      }
    }
  }

  const time = clock(state.minute);
  const id = state.nextId;
  return {
    sent: {
      entries,
      awaiting,
      used,
      messages: [...state.messages, { id, kind: "sent", time, ...you }],
      minute: state.minute + 1,
      nextId: id + 1 + replies.length,
    },
    replies: replies.map((reply, index) => ({ ...reply, id: id + 1 + index, time })),
  };
}

export const deliver = (state: ChatState, replies: readonly Message[]): ChatState => ({
  ...state,
  messages: [...state.messages, ...replies],
});
