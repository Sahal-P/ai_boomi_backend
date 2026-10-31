"use client";

import { ArrowUp, Check, Languages, Mic, Square, X } from "lucide-react";
import type { RefObject } from "react";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { ThinkingOrb } from "@/components/feedback/thinking-orb";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuLabel,
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import type { VoiceState } from "@/hooks/use-voice-recorder";
import { RECORDING_LIMITS, styles, type DisplayStyle } from "@/lib/api/assistant";
import { cn } from "@/lib/utils";

export const styleLabels: Record<DisplayStyle, { label: string; short: string; lang?: string }> = {
  auto: { label: "Match my question", short: "Auto" },
  en: { label: "English", short: "English" },
  hi: { label: "हिन्दी", short: "हिन्दी", lang: "hi" },
  hinglish: { label: "Hinglish", short: "Hinglish" },
  ml: { label: "മലയാളം", short: "മലയാളം", lang: "ml" },
  manglish: { label: "Manglish", short: "Manglish" },
};

const languageNames: Record<string, string> = { en: "English", hi: "Hindi", ml: "Malayalam" };

function clock(ms: number) {
  const seconds = Math.max(0, Math.floor(ms / 1000));
  return `0:${String(seconds).padStart(2, "0")}`;
}

type Voice = {
  state: VoiceState;
  level: number;
  start: () => void;
  stop: () => void;
  cancel: () => void;
};

/** The reply language, as a small chip inside the composer. */
function StyleMenu({ style, onStyle }: { style: DisplayStyle; onStyle: (style: DisplayStyle) => void }) {
  const current = styleLabels[style];
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          aria-label={`Reply style, ${current.short}`}
          className="h-10 gap-1.5 rounded-full px-3 text-ink-soft hover:text-ink"
        >
          <Languages aria-hidden="true" />
          <span lang={current.lang}>{current.short}</span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent side="top" align="start" className="w-56 rounded-2xl p-2">
        <DropdownMenuLabel className="px-2 py-1.5 text-xs font-medium text-ink-soft">Reply style</DropdownMenuLabel>
        <DropdownMenuRadioGroup
          value={style}
          onValueChange={(value) => {
            const next = styles.find((item) => item === value);
            if (next) onStyle(next);
          }}
        >
          {styles.map((item) => (
            <DropdownMenuRadioItem key={item} value={item} className="min-h-10" lang={styleLabels[item].lang}>
              {styleLabels[item].label}
            </DropdownMenuRadioItem>
          ))}
        </DropdownMenuRadioGroup>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/** Recording, permission and transcription, shown over the text while they run. */
function VoiceStrip({ voice }: { voice: Voice }) {
  const { state } = voice;
  const remaining = state.step === "recording" ? RECORDING_LIMITS.seconds * 1000 - state.elapsed : 0;
  return (
    <div className="absolute inset-x-1.5 top-1.5 bottom-[3.25rem] flex items-center gap-3 rounded-[12px] bg-white/95 px-3 text-sm">
      {state.step === "requesting" && (
        <>
          <span role="status" className="min-w-0 flex-1">Waiting for microphone permission — answer your browser&apos;s prompt.</span>
          <Button type="button" size="icon-sm" variant="ghost" aria-label="Cancel" onClick={voice.cancel}>
            <X aria-hidden="true" />
          </Button>
        </>
      )}
      {state.step === "recording" && (
        <>
          <span className="size-2.5 shrink-0 rounded-full bg-negative motion-safe:animate-pulse" aria-hidden="true" />
          <span role="status" className="shrink-0 font-semibold tabular-nums">
            Recording · {clock(state.elapsed)}
            <span className="sr-only"> ({clock(remaining)} left)</span>
          </span>
          {/* The real microphone level, the honest signal that it is listening. */}
          <span className="flex h-6 min-w-0 flex-1 items-center gap-[3px]" aria-hidden="true">
            {[0.55, 0.8, 1, 0.7, 0.9, 0.6, 0.85, 0.65, 1, 0.75].map((weight, index) => (
              <span
                key={index}
                className="w-[3px] rounded-full bg-ink transition-[height] duration-100"
                style={{ height: `${Math.max(12, Math.round(voice.level * weight * 100))}%` }}
              />
            ))}
          </span>
          <Button type="button" size="sm" className="h-9 shrink-0" onClick={voice.stop}>
            <Check aria-hidden="true" /> Stop and transcribe
          </Button>
          <Button type="button" size="icon-sm" variant="ghost" aria-label="Discard" onClick={voice.cancel}>
            <X aria-hidden="true" />
          </Button>
        </>
      )}
      {state.step === "transcribing" && (
        <>
          <ThinkingOrb state="listening" size={20} />
          <span role="status" className="min-w-0 flex-1">Transcribing your recording…</span>
          <Button type="button" size="icon-sm" variant="ghost" aria-label="Cancel" onClick={voice.cancel}>
            <X aria-hidden="true" />
          </Button>
        </>
      )}
    </div>
  );
}

/**
 * Ask's composer: a glass bubble with the question, the reply style, the mic and Ask (Stop while
 * an answer is on its way). Enter sends and Shift+Enter breaks the line; nothing recorded is sent
 * until you press Ask.
 */
export function Composer({
  id,
  inputRef,
  value,
  onChange,
  onSubmit,
  pending,
  onStop,
  style,
  onStyle,
  voice,
  fromVoice,
  onDiscardTranscript,
}: {
  id: string;
  inputRef: RefObject<HTMLTextAreaElement | null>;
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  pending: boolean;
  onStop: () => void;
  style: DisplayStyle;
  onStyle: (style: DisplayStyle) => void;
  voice: Voice;
  fromVoice: boolean;
  onDiscardTranscript: () => void;
}) {
  const { state } = voice;
  const voiceBusy = state.step === "requesting" || state.step === "recording" || state.step === "transcribing";
  return (
    <div>
      <form
        className="relative"
        onSubmit={(event) => {
          event.preventDefault();
          if (!pending && !voiceBusy) onSubmit();
        }}
      >
        <label htmlFor={id} className="sr-only">
          {fromVoice ? "Your question (from your recording — check it)" : "Your question"}
        </label>
        <textarea
          id={id}
          ref={inputRef}
          value={value}
          rows={1}
          maxLength={2000}
          enterKeyHint="send"
          placeholder="Ask about your money…"
          disabled={voiceBusy}
          onChange={(event) => onChange(event.target.value)}
          onKeyDown={(event) => {
            // Enter that picks a word in a Hindi or Malayalam input method (229 in Safari) is left alone.
            if (event.key !== "Enter" || event.shiftKey) return;
            if (event.nativeEvent.isComposing || event.keyCode === 229) return;
            event.preventDefault();
            if (!pending && value.trim()) onSubmit();
          }}
          className="composer block max-h-60 min-h-[6.5rem] w-full resize-none rounded-xl px-4 pt-4 pb-[3.75rem] text-base leading-relaxed field-sizing-content disabled:cursor-default"
        />
        {voiceBusy && <VoiceStrip voice={voice} />}
        <div className="absolute inset-x-2 bottom-2 flex items-center gap-1">
          <StyleMenu style={style} onStyle={onStyle} />
          <span className="flex-1" />
          <Button
            type="button"
            variant="ghost"
            size="icon"
            aria-label={state.step === "review" ? "Record again" : "Record a question"}
            className="size-10 text-ink-soft hover:text-ink"
            disabled={pending || voiceBusy}
            onClick={voice.start}
          >
            <Mic className="size-5" aria-hidden="true" />
          </Button>
          {pending ? (
            <Button type="button" size="icon" aria-label="Stop" className="size-10" onClick={onStop}>
              <Square className="size-3.5 fill-current" aria-hidden="true" />
            </Button>
          ) : (
            <Button type="submit" size="icon" aria-label="Ask" className="size-10" disabled={voiceBusy || !value.trim()}>
              <ArrowUp className="size-5" aria-hidden="true" />
            </Button>
          )}
        </div>
      </form>
      {state.step === "review" && (
        <p role="status" className={cn("mt-2 flex flex-wrap items-center gap-x-2 text-xs text-ink-soft")}>
          Transcript ready{languageNames[state.language] ? ` (${languageNames[state.language]})` : ""}. Check or edit it, then press
          Ask — nothing is sent until you do.
          <Button type="button" variant="link" size="sm" className="h-auto px-0 text-xs text-ink" onClick={onDiscardTranscript}>
            Discard transcript
          </Button>
        </p>
      )}
      {state.step === "error" && <ProblemNotice className="mt-2" problem={state.problem} />}
    </div>
  );
}
