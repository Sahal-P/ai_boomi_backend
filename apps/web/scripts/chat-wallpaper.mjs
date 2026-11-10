// FinBoy's chat wallpaper (public/brand/chat-wallpaper.svg): everyday-money doodles laid out the
// way a chat wallpaper is, drawn from Lucide's icon shapes (ISC licence, lucide.dev). It is
// FinBoy's own pattern, not WhatsApp's doodle art. Run from apps/web:
//   node scripts/chat-wallpaper.mjs
import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const ICONS = [
  "coffee", "bus", "indian-rupee", "receipt", "piggy-bank", "smartphone",
  "milk", "carrot", "wallet", "umbrella", "car", "gift",
  "coins", "shopping-bag", "sun", "banknote", "bike", "heart",
  "calculator", "apple", "fuel", "house", "star", "pill",
  "book-open", "cake", "cloud", "shirt", "leaf", "eighth-notes",
  "mail", "tag", "calendar", "bell", "camera", "pizza",
];
const TILE = 280;
const GRID = 6;
const CELL = TILE / GRID;
// A shade darker than the wa-wallpaper beige (#efeae2), as WhatsApp's doodles sit on theirs.
const INK = "#e1d7c7";

// A fixed seed: the same tile on every run.
let seed = 20261110;
const random = () => {
  seed = (seed * 1664525 + 1013904223) % 2 ** 32;
  return seed / 2 ** 32;
};

const escape = (value) => String(value).replace(/&/g, "&amp;").replace(/"/g, "&quot;");
const element = ([tag, attributes]) =>
  `<${tag} ${Object.entries(attributes)
    .filter(([name]) => name !== "key")
    .map(([name, value]) => `${name}="${escape(value)}"`)
    .join(" ")}/>`;

const groups = [];
for (const [index, name] of ICONS.entries()) {
  const { __iconData } = await import(`lucide-react/dist/esm/icons/${name}.mjs`);
  const scale = 0.78 + random() * 0.3; // 19–26 px from Lucide's 24 px grid
  const size = 24 * scale;
  const reach = size * 0.72; // half the diagonal of a rotated icon, so none crosses its cell
  const column = index % GRID;
  const row = Math.floor(index / GRID);
  const slack = Math.max(0, CELL / 2 - reach);
  const x = column * CELL + CELL / 2 + (random() * 2 - 1) * slack;
  const y = row * CELL + CELL / 2 + (random() * 2 - 1) * slack;
  const turn = Math.round((random() * 2 - 1) * 28);
  const shapes = __iconData.node.map(element).join("");
  groups.push(
    `<g transform="translate(${(x - size / 2).toFixed(1)} ${(y - size / 2).toFixed(1)}) rotate(${turn} ${(size / 2).toFixed(1)} ${(size / 2).toFixed(1)}) scale(${scale.toFixed(3)})" stroke-width="${(1.35 / scale).toFixed(2)}">${shapes}</g>`,
  );
}

const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${TILE}" height="${TILE}" viewBox="0 0 ${TILE} ${TILE}" fill="none" stroke="${INK}" stroke-linecap="round" stroke-linejoin="round"><!-- FinBoy's chat wallpaper from Lucide icons (ISC licence, lucide.dev), laid out by apps/web/scripts/chat-wallpaper.mjs. -->${groups.join("")}</svg>\n`;
const target = fileURLToPath(new URL("../public/brand/chat-wallpaper.svg", import.meta.url));
writeFileSync(target, svg);
console.log(`chat-wallpaper.svg: ${ICONS.length} doodles, ${svg.length} bytes`);
