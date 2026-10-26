"use client";

import { Mic, Square, X } from "lucide-react";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { ThinkingOrb } from "@/components/feedback/thinking-orb";
import { Button } from "@/components/ui/button";
import type { VoiceState } from "@/hooks/use-voice-recorder";
import { RECORDING_LIMITS } from "@/lib/api/assistant";

const languageNames: Record<string, string> = { en: "English", hi: "Hindi", ml: "Malayalam" };

function clock(ms: number) {
  const seconds = Math.max(0, Math.floor(ms / 1000));
  return `0:${String(seconds).padStart(2, "0")}`;
}

/** The visible voice state machine: nothing records without a tap, and every step can be cancelled. */
export function VoiceControls({
  state,
  level,
  disabled,
  onStart,
  onStop,
  onCancel,
  onDiscardTranscript,
}: {
  state: VoiceState;
  level: number;
  disabled: boolean;
  onStart: () => void;
  onStop: () => void;
  onCancel: () => void;
  onDiscardTranscript: () => void;
}) {
  const remaining = state.step === "recording" ? RECORDING_LIMITS.seconds * 1000 - state.elapsed : 0;
  return (
    <div className="space-y-3">
      {state.step === "idle" || state.step === "review" || state.step === "error" ? (
        <div className="flex flex-wrap items-center gap-2">
          <Button type="button" variant="outline" disabled={disabled} onClick={onStart}>
            <Mic aria-hidden="true" /> {state.step === "review" ? "Record again" : "Record a question"}
          </Button>
          {state.step === "review" && (
            <Button type="button" variant="ghost" onClick={onDiscardTranscript}>
              Discard transcript
            </Button>
          )}
        </div>
      ) : null}

      {state.step === "requesting" && (
        <div className="flex flex-wrap items-center gap-3 rounded-2xl bg-well p-3 text-sm ring-1 ring-ink/5">
          <span role="status">Waiting for microphone permission — answer your browser&apos;s prompt.</span>
          <Button type="button" size="sm" variant="ghost" onClick={onCancel}>
            <X aria-hidden="true" /> Cancel
          </Button>
        </div>
      )}

      {state.step === "recording" && (
        <div className="rounded-2xl border border-ink/15 bg-white/55 p-3">
          <div className="flex flex-wrap items-center gap-3">
            <span className="flex items-center gap-2 text-sm font-semibold" role="status">
              <span className="size-2.5 rounded-full bg-negative motion-safe:animate-pulse" aria-hidden="true" />
              Recording · {clock(state.elapsed)}
              <span className="font-normal text-ink-soft">({clock(remaining)} left)</span>
            </span>
            <div className="ml-auto flex gap-2">
              <Button type="button" size="sm" onClick={onStop}>
                <Square aria-hidden="true" /> Stop and transcribe
              </Button>
              <Button type="button" size="sm" variant="ghost" onClick={onCancel}>
                Discard
              </Button>
            </div>
          </div>
          <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white" aria-hidden="true">
            <div className="h-full rounded-full bg-ink transition-[width] duration-100" style={{ width: `${Math.round(level * 100)}%` }} />
          </div>
          <p className="mt-2 text-xs text-ink-soft">
            Stops by itself at {RECORDING_LIMITS.seconds} seconds. The recording stays on this device until you stop it, and FinBoy doesn&apos;t keep it.
          </p>
        </div>
      )}

      {state.step === "transcribing" && (
        <div className="flex flex-wrap items-center gap-3 rounded-2xl bg-well p-3 text-sm ring-1 ring-ink/5">
          <ThinkingOrb state="listening" size={20} />
          <span role="status">Transcribing your recording…</span>
          <Button type="button" size="sm" variant="ghost" onClick={onCancel}>
            <X aria-hidden="true" /> Cancel
          </Button>
        </div>
      )}

      {state.step === "review" && (
        <p role="status" className="text-sm text-ink-soft">
          Transcript ready{languageNames[state.language] ? ` (${languageNames[state.language]})` : ""}. Check or edit
          it above, then press Ask — nothing is sent until you do.
        </p>
      )}

      {state.step === "error" && <ProblemNotice problem={state.problem} />}
    </div>
  );
}
