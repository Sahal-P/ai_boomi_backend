"use client";

import { ThinkingOrb } from "@/components/feedback/thinking-orb";
import { cn } from "@/lib/utils";
import { Art, RupeeCoin, ShadedDisc, Sparkle, SUNFLOWER } from "./kit";

const dot = { fill: "currentColor", stroke: "none" } as const;

/**
 * A WhatsApp bubble, its tail at the top outer corner as WhatsApp draws it (`out` is yours, on
 * the right). Corners are 6 units, the tail 5 wide and 6 deep.
 */
function bubble(x: number, y: number, w: number, h: number, side: "out" | "in") {
  const r = 6;
  return side === "out"
    ? `M${x + r} ${y}H${x + w + 5}L${x + w} ${y + 6}V${y + h - r}Q${x + w} ${y + h} ${x + w - r} ${y + h}H${x + r}Q${x} ${y + h} ${x} ${y + h - r}V${y + r}Q${x} ${y} ${x + r} ${y}Z`
    : `M${x + w - r} ${y}H${x - 5}L${x} ${y + 6}V${y + h - r}Q${x} ${y + h} ${x + r} ${y + h}H${x + w - r}Q${x + w} ${y + h} ${x + w} ${y + h - r}V${y + r}Q${x + w} ${y} ${x + w - r} ${y}Z`;
}

/**
 * Sign-in and the landing hero: a phone showing FinBoy's WhatsApp chat in WhatsApp's own colours
 * (the wa-* tokens) — your voice note, FinBoy's reply with a live composing orb, a reply with its
 * button, the message bar and mic — beside a receipt, an envelope and the ₹ coin in sunflower.
 */
export function MoneyScene({ className }: { className?: string }) {
  return (
    <div className={cn("relative aspect-[320/230] text-ink", className)}>
      <Art viewBox="0 0 320 230" className="absolute inset-0 size-full">
        {(dots) => (
          <>
            <g transform="rotate(-12 38 140)">
              <rect x="6" y="118" width="64" height="44" rx="6" fill="#fff" />
              <path d="M6 124l32 21 32-21" />
            </g>
            <g transform="rotate(9 246 70)">
              <path d="M210 18H282Q288 18 288 24V118l-7 7-7-7-7 7-7-7-7 7-7-7-7 7-7-7-7 7-7-7-7 7-7-7V24Q204 18 210 18Z" fill="#fff" />
              <path d="M218 40h54M218 54h40M218 68h48" />
              <rect x="218" y="84" width="42" height="13" rx="6.5" fill={SUNFLOWER} strokeWidth={2} />
            </g>
            <rect x="58" y="10" width="118" height="210" rx="22" fill="#fff" />
            {/* The chat: WhatsApp's wallpaper under a white top bar (back, FinBoy's photo, name, menu). */}
            <rect x="68" y="24" width="98" height="182" rx="13" fill="var(--wa-wallpaper)" stroke="none" />
            <path d="M68 39V37a13 13 0 0 1 13-13h72a13 13 0 0 1 13 13v2z" fill="var(--wa-bar)" stroke="none" />
            <path d="M68 39h98" strokeWidth={1.5} />
            <rect x="68" y="24" width="98" height="182" rx="13" strokeWidth={1.5} />
            <rect x="101" y="16" width="32" height="5" rx="2.5" {...dot} />
            <path d="M76 28.5l-3 3 3 3" strokeWidth={1.4} />
            <circle cx="84" cy="31.5" r="4.5" fill={SUNFLOWER} strokeWidth={1.2} />
            <path d="M92.5 31.5h19" strokeWidth={2.2} />
            <circle cx="159" cy="28" r="0.9" {...dot} />
            <circle cx="159" cy="31.5" r="0.9" {...dot} />
            <circle cx="159" cy="35" r="0.9" {...dot} />
            {/* Your voice note: play, WhatsApp's green knob, the waveform. */}
            <path d={bubble(90, 45, 66, 24, "out")} fill="var(--wa-out)" strokeWidth={2} />
            <path d="M97.5 52.5l7 4.5-7 4.5z" fill="currentColor" strokeWidth={1.2} />
            <circle cx="111" cy="57" r="2.4" fill="var(--wa-accent)" stroke="none" />
            <path d="M116 54.5v5M120.5 51.5v11M125 55v4M129.5 51v12M134 53.5v7M138.5 55.5v3M143 54v6M147.5 55.5v3" strokeWidth={2} />
            {/* FinBoy's reply (the orb composes in its empty left side), then a reply with its button. */}
            <path d={bubble(78, 80, 76, 40, "in")} fill="var(--wa-in)" strokeWidth={2} />
            <path d="M106 94h36M106 106h24" strokeWidth={2.2} />
            <rect x="78" y="125" width="76" height="52" rx="6" fill="var(--wa-in)" strokeWidth={2} />
            <path d="M87 137h34" strokeWidth={2.2} />
            <path d="M78 151h76" strokeWidth={1.2} />
            <path d="M104 164h24" stroke="var(--wa-button)" strokeWidth={2.4} />
            {/* WhatsApp's message bar and its green mic. */}
            <rect x="72" y="184" width="70" height="15" rx="7.5" fill="var(--wa-bar)" strokeWidth={1.8} />
            <circle cx="154" cy="191.5" r="7.5" fill="var(--wa-accent)" strokeWidth={1.8} />
            <path d="M154 187.4v4.2" stroke="#fff" strokeWidth={2.6} />
            <path d="M151.3 190.9a2.7 2.7 0 0 0 5.4 0M154 193.6v1.5" stroke="#fff" strokeWidth={1.2} />
            <RupeeCoin x={214} y={166} r={46} dots={dots} />
            <path d="M254 126l9-9M261 142l12-2M244 117l2-12" />
            <Sparkle x={30} y={46} r={12} />
            <Sparkle x={296} y={150} r={8} />
            <Sparkle x={38} y={196} r={7} />
            <circle cx="300" cy="100" r="2.5" {...dot} />
            <circle cx="20" cy="104" r="2" {...dot} />
          </>
        )}
      </Art>
      {/* Centred on the reply bubble's empty left side (92, 100); 20 px fits it at any width. */}
      <div className="absolute -translate-x-1/2 -translate-y-1/2" style={{ left: "28.75%", top: "43.5%" }}>
        <ThinkingOrb state="composing" size={20} rest />
      </div>
    </div>
  );
}

/** No records yet: an open envelope with an empty letter, and the ₹ coin waiting. */
export function NoRecordsArt({ className }: { className?: string }) {
  return (
    <Art viewBox="0 0 240 170" className={cn("text-ink", className)}>
      {(dots) => (
        <>
          <path d="M52 82L120 36L188 82Z" fill="#fff" />
          <path d="M52 82L120 36L188 82Z" fill={dots} stroke="none" />
          <rect x="74" y="48" width="92" height="62" rx="8" fill="#fff" />
          <path d="M88 66h44M88 80h30" strokeWidth={2.4} strokeDasharray="0.5 6" />
          <path d="M52 82V146a10 10 0 0 0 10 10H178a10 10 0 0 0 10-10V82L120 124Z" fill="#fff" />
          <path d="M52 148l50-38M188 148l-50-38" strokeWidth={2} />
          <RupeeCoin x={196} y={138} r={22} dots={dots} />
          <Sparkle x={34} y={42} r={10} />
          <Sparkle x={208} y={34} r={8} />
          <Sparkle x={26} y={128} r={6} />
        </>
      )}
    </Art>
  );
}

/** Nothing matches: a sunflower lens over a stack of record cards. */
export function NoMatchArt({ className }: { className?: string }) {
  return (
    <Art viewBox="0 0 240 170" className={cn("text-ink", className)}>
      {(dots) => (
        <>
          <rect x="40" y="38" width="118" height="84" rx="12" fill="#fff" transform="rotate(-7 99 80)" />
          <rect x="56" y="52" width="118" height="84" rx="12" fill="#fff" />
          <path d="M72 74h56M72 88h40M72 102h48" strokeWidth={2.2} />
          <rect x="72" y="114" width="30" height="11" rx="5.5" fill={dots} strokeWidth={2} />
          <path d="M190 122l22 22" strokeWidth={9} />
          <circle cx="168" cy="98" r="30" fill="#fff" strokeWidth={3} />
          <circle cx="168" cy="98" r="22" fill={SUNFLOWER} strokeWidth={2} />
          <path d="M155 89a15 15 0 0 1 13-7" stroke="#fff" strokeWidth={3} />
          <Sparkle x={34} y={142} r={8} />
          <Sparkle x={214} y={40} r={10} />
          <circle cx="206" cy="66" r="2.5" {...dot} />
        </>
      )}
    </Art>
  );
}

/** All reviewed: a check stamp, the ₹ coin and a little confetti. */
export function AllReviewedArt({ className }: { className?: string }) {
  return (
    <Art viewBox="0 0 240 170" className={cn("text-ink", className)}>
      {(dots) => (
        <>
          <ShadedDisc x={110} y={86} r={58} dots={dots} />
          <circle cx="110" cy="86" r="46" fill={SUNFLOWER} strokeWidth={2} strokeDasharray="2 6" />
          <path d="M86 88l17 17 31-35" strokeWidth={7} />
          <RupeeCoin x={182} y={130} r={24} dots={dots} />
          <rect x="34" y="34" width="12" height="6" rx="2" fill={SUNFLOWER} strokeWidth={2} transform="rotate(24 40 37)" />
          <rect x="196" y="72" width="12" height="6" rx="2" fill={SUNFLOWER} strokeWidth={2} transform="rotate(-18 202 75)" />
          <rect x="40" y="128" width="10" height="5" rx="2" {...dot} transform="rotate(-30 45 130)" />
          <Sparkle x={196} y={38} r={11} />
          <Sparkle x={30} y={96} r={7} />
          <Sparkle x={62} y={152} r={6} />
        </>
      )}
    </Art>
  );
}

/** Nothing this month: an empty calendar page and the ₹ coin. */
export function EmptyMonthArt({ className }: { className?: string }) {
  return (
    <Art viewBox="0 0 240 170" className={cn("text-ink", className)}>
      {(dots) => (
        <>
          <rect x="56" y="34" width="120" height="112" rx="12" fill="#fff" />
          <path d="M56 64V46a12 12 0 0 1 12-12H164a12 12 0 0 1 12 12V64Z" fill={SUNFLOWER} />
          <path d="M86 24v18M146 24v18" strokeWidth={4} />
          {[82, 104, 126].flatMap((y) =>
            [76, 96, 116, 136, 156].map((x) => <circle key={`${x}-${y}`} cx={x} cy={y} r="4" strokeWidth={2} />),
          )}
          <RupeeCoin x={182} y={128} r={24} dots={dots} />
          <Sparkle x={34} y={52} r={10} />
          <Sparkle x={212} y={44} r={7} />
          <circle cx="28" cy="120" r="2" {...dot} />
        </>
      )}
    </Art>
  );
}
