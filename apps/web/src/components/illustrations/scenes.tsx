"use client";

import { ThinkingOrb } from "@/components/feedback/thinking-orb";
import { cn } from "@/lib/utils";
import { Art, RupeeCoin, ShadedDisc, Sparkle, SUNFLOWER } from "./kit";

const dot = { fill: "currentColor", stroke: "none" } as const;

/**
 * Sign-in and the landing hero: a phone with your voice note and FinBoy's reply — a live
 * composing orb sits in the reply bubble — beside a receipt, an envelope and the ₹ coin.
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
            <rect x="68" y="24" width="98" height="182" rx="13" strokeWidth={1.5} />
            <rect x="101" y="16" width="32" height="5" rx="2.5" {...dot} />
            <rect x="86" y="42" width="72" height="26" rx="13" fill={SUNFLOWER} strokeWidth={2} />
            <path d="M96 49.5l8.5 5.5-8.5 5.5z" fill="currentColor" strokeWidth={1.2} />
            <path d="M112 52v6M118 49v12M124 52.5v5M130 48v14M136 51v8M142 53v4M148 51.5v7" strokeWidth={2.2} />
            <rect x="76" y="80" width="78" height="40" rx="14" fill="#fff" strokeWidth={2} />
            <path d="M106 94h36M106 106h24" strokeWidth={2.2} />
            <rect x="86" y="134" width="72" height="50" rx="11" fill="#fff" strokeWidth={2} />
            <path d="M96 148h30" strokeWidth={2.2} />
            <rect x="96" y="158" width="52" height="15" rx="7.5" fill={dots} strokeWidth={2} />
            <path d="M100 198h34" strokeWidth={3} />
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
      {/* Centred on the reply bubble's empty left side (91, 100); 20 px fits it at any width. */}
      <div className="absolute -translate-x-1/2 -translate-y-1/2" style={{ left: "28.4%", top: "43.5%" }}>
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
