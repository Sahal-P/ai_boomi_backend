"use client";

import { Mic, Pause, Play, User } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { BrandMark } from "@/components/brand";
import type { Clip } from "@/lib/chat-demo/script";
import { cn } from "@/lib/utils";

import { Bubble, Meta, Spacer } from "./bubbles";

const length = (seconds: number) => `0:${String(Math.floor(seconds)).padStart(2, "0")}`;

/**
 * WhatsApp's voice message: play, the waveform with its green knob, the length (the time played
 * while it plays), the sender's photo with a mic that turns blue once played, and for yours the
 * transcript underneath. The parent keeps one playing at a time.
 */
export function VoiceNote({
  from,
  clip,
  time,
  tail,
  playing,
  onToggle,
}: {
  from: "you" | "finboy";
  clip: Clip;
  time: string;
  tail: boolean;
  playing: boolean;
  onToggle: (playing: boolean) => void;
}) {
  const audio = useRef<HTMLAudioElement>(null);
  const toggle = useRef(onToggle);
  const [progress, setProgress] = useState(0);
  // FinBoy has heard your note (it read it); FinBoy's turns blue once you play it.
  const [heard, setHeard] = useState(from === "you");
  const you = from === "you";

  useEffect(() => {
    toggle.current = onToggle;
  }, [onToggle]);

  useEffect(() => {
    const element = audio.current;
    if (!element) return;
    if (!playing) {
      element.pause();
      return;
    }
    let frame = 0;
    const tick = () => {
      if (element.duration) setProgress(element.currentTime / element.duration);
      frame = requestAnimationFrame(tick);
    };
    element.play().then(
      () => {
        frame = requestAnimationFrame(tick);
      },
      () => toggle.current(false),
    );
    return () => cancelAnimationFrame(frame);
  }, [playing]);

  const ended = () => {
    if (audio.current) audio.current.currentTime = 0;
    setProgress(0);
    setHeard(true);
    toggle.current(false);
  };
  const shown = playing || progress > 0 ? progress * clip.seconds : Math.round(clip.seconds);
  const who = you ? "your" : "FinBoy's";

  return (
    <Bubble from={from} tail={tail} className="w-[16.5rem] px-2 pt-2 pb-1.5">
      <span className="sr-only">
        {you ? "You" : "FinBoy"}: Voice note, “{clip.words}”
      </span>
      <audio ref={audio} src={clip.src} preload="none" onEnded={ended} />
      <div className="flex items-center gap-2">
        <button
          type="button"
          aria-label={`Play ${who} voice note`}
          aria-pressed={playing}
          onClick={() => onToggle(!playing)}
          className="grid size-9 shrink-0 place-items-center rounded-full text-wa-meta outline-none focus-visible:outline-2 focus-visible:outline-wa-button"
        >
          {playing ? (
            <Pause className="size-7 fill-current" strokeWidth={1.5} aria-hidden="true" />
          ) : (
            <Play className="size-7 fill-current" strokeWidth={1.5} aria-hidden="true" />
          )}
        </button>
        <div aria-hidden="true" className="min-w-0 flex-1">
          <div className="relative flex h-6 items-center">
            <svg
              viewBox={`0 0 ${clip.bars.length * 4} 20`}
              preserveAspectRatio="none"
              className="h-5 w-full"
            >
              {clip.bars.map((height, index) => (
                <rect
                  key={index}
                  x={index * 4 + 1}
                  y={(20 - height) / 2}
                  width="2"
                  height={height}
                  rx="1"
                  className={index / clip.bars.length < progress ? "fill-wa-meta" : "fill-black/25"}
                />
              ))}
            </svg>
            <span
              className="absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full bg-wa-accent"
              style={{ left: `calc(6px + ${progress} * (100% - 12px))` }}
            />
          </div>
          <p className="mt-0.5 text-[11px] leading-4 text-wa-meta">{length(shown)}</p>
        </div>
        <span aria-hidden="true" className="relative shrink-0">
          {you ? (
            <span className="grid size-11 items-end justify-items-center overflow-hidden rounded-full bg-wa-avatar text-white">
              <User className="size-9 translate-y-1.5 fill-current" strokeWidth={1} />
            </span>
          ) : (
            <span className="block size-11 overflow-hidden rounded-full">
              <BrandMark className="size-full" />
            </span>
          )}
          <Mic
            className={cn("absolute -bottom-0.5 -left-1.5 size-4", heard ? "text-wa-played" : "text-wa-accent")}
            strokeWidth={2.5}
          />
        </span>
      </div>
      {you ? (
        <p aria-hidden="true" className="mt-1.5 px-0.5 text-wa-meta">
          “{clip.words}”
          <Spacer sent />
        </p>
      ) : (
        <Spacer />
      )}
      <Meta time={time} sent={you} />
    </Bubble>
  );
}
