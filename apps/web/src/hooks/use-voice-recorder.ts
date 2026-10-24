"use client";

import { useEffect, useRef, useState } from "react";
import { RECORDING_LIMITS, transcribeAudio } from "@/lib/api/assistant";
import { isAbort } from "@/lib/api/http";
import { describeProblem, type Problem } from "@/lib/messages";

export type VoiceState =
  | { step: "idle" }
  | { step: "requesting" }
  | { step: "recording"; elapsed: number }
  | { step: "transcribing" }
  | { step: "review"; language: string }
  | { step: "error"; problem: Problem; permission: "denied" | "missing" | "unsupported" | null };

const MAX_MS = RECORDING_LIMITS.seconds * 1000 - 500;

function micProblem(error: unknown): VoiceState {
  const name = error instanceof DOMException ? error.name : "";
  if (name === "NotAllowedError" || name === "SecurityError") {
    return {
      step: "error",
      permission: "denied",
      problem: {
        title: "Microphone access is blocked",
        detail: "Allow the microphone for this site in your browser's settings, then try again — or type your question.",
        reference: null,
        kind: "unknown",
        code: null,
      },
    };
  }
  if (name === "NotFoundError" || name === "OverconstrainedError") {
    return {
      step: "error",
      permission: "missing",
      problem: { title: "No microphone found", detail: "Connect a microphone and try again, or type your question.", reference: null, kind: "unknown", code: null },
    };
  }
  return {
    step: "error",
    permission: null,
    problem: {
      title: "The microphone couldn't start",
      detail: "Another app may be using it. Try again, or type your question.",
      reference: null,
      kind: "unknown",
      code: null,
    },
  };
}

/**
 * Explicit voice capture: permission → recording (countdown, level, stop/cancel) → transcript
 * review. Audio stays in memory, is never auto-sent as a question, and every track, timer and
 * audio context is released when recording ends or the page closes.
 */
export function useVoiceRecorder(onTranscript: (text: string) => void) {
  const [state, setState] = useState<VoiceState>({ step: "idle" });
  const [level, setLevel] = useState(0);
  const session = useRef<{
    cancelled: boolean;
    stream: MediaStream | null;
    recorder: MediaRecorder | null;
    timer: ReturnType<typeof setInterval> | null;
    audio: AudioContext | null;
    frame: number | null;
    transcribe: AbortController | null;
    discard: boolean;
  } | null>(null);
  const deliver = useRef(onTranscript);
  useEffect(() => {
    deliver.current = onTranscript;
  });

  function release() {
    const current = session.current;
    if (!current) return;
    if (current.timer) clearInterval(current.timer);
    if (current.frame !== null) cancelAnimationFrame(current.frame);
    current.stream?.getTracks().forEach((track) => track.stop());
    void current.audio?.close().catch(() => undefined);
    current.stream = null;
    current.audio = null;
    current.timer = null;
    current.frame = null;
    setLevel(0);
  }

  useEffect(
    () => () => {
      const current = session.current;
      if (!current) return;
      current.cancelled = true;
      current.discard = true;
      current.transcribe?.abort();
      if (current.recorder?.state === "recording") current.recorder.stop();
      if (current.timer) clearInterval(current.timer);
      if (current.frame !== null) cancelAnimationFrame(current.frame);
      current.stream?.getTracks().forEach((track) => track.stop());
      void current.audio?.close().catch(() => undefined);
    },
    [],
  );

  async function transcribe(blob: Blob) {
    const controller = new AbortController();
    if (session.current) session.current.transcribe = controller;
    setState({ step: "transcribing" });
    try {
      const result = await transcribeAudio(blob, controller.signal);
      if (controller.signal.aborted) return;
      if (!result.transcript.trim()) {
        setState({
          step: "error",
          permission: null,
          problem: { title: "No words were recognised", detail: "Try recording again a little closer to the microphone, or type your question.", reference: null, kind: "unknown", code: null },
        });
        return;
      }
      deliver.current(result.transcript.trim());
      setState({ step: "review", language: result.detected_language });
    } catch (error) {
      if (isAbort(error) || controller.signal.aborted) {
        setState({ step: "idle" });
        return;
      }
      setState({ step: "error", permission: null, problem: describeProblem(error, "Your recording couldn't be transcribed") });
    }
  }

  async function start() {
    if (state.step === "requesting" || state.step === "recording" || state.step === "transcribing") return;
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setState({
        step: "error",
        permission: "unsupported",
        problem: { title: "Recording isn't supported in this browser", detail: "Type your question instead.", reference: null, kind: "unknown", code: null },
      });
      return;
    }
    const current = { cancelled: false, stream: null, recorder: null, timer: null, audio: null, frame: null, transcribe: null, discard: false } as NonNullable<typeof session.current>;
    session.current = current;
    setState({ step: "requesting" });
    let stream: MediaStream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (error) {
      if (!current.cancelled) setState(micProblem(error));
      return;
    }
    if (current.cancelled) {
      // Permission arrived after Cancel: release the microphone immediately.
      stream.getTracks().forEach((track) => track.stop());
      return;
    }
    current.stream = stream;
    const chunks: Blob[] = [];
    let size = 0;
    let tooLarge = false;
    const options = MediaRecorder.isTypeSupported("audio/webm;codecs=opus") ? { mimeType: "audio/webm;codecs=opus" } : undefined;
    const recorder = new MediaRecorder(stream, options);
    current.recorder = recorder;
    recorder.ondataavailable = (event) => {
      size += event.data.size;
      if (size > RECORDING_LIMITS.bytes) {
        tooLarge = true;
        if (recorder.state === "recording") recorder.stop();
      } else if (event.data.size) chunks.push(event.data);
    };
    recorder.onstop = () => {
      release();
      if (current.discard || current.cancelled) {
        setState({ step: "idle" });
        return;
      }
      if (tooLarge) {
        setState({
          step: "error",
          permission: null,
          problem: { title: "That recording was too large", detail: "Try a shorter question (up to 30 seconds), or type it.", reference: null, kind: "unknown", code: null },
        });
        return;
      }
      const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
      if (!blob.size) {
        setState({
          step: "error",
          permission: null,
          problem: { title: "No audio was captured", detail: "Check your microphone and try again, or type your question.", reference: null, kind: "unknown", code: null },
        });
        return;
      }
      void transcribe(blob);
    };
    recorder.onerror = () => {
      current.discard = true;
      if (recorder.state === "recording") recorder.stop();
      setState({
        step: "error",
        permission: null,
        problem: { title: "Recording stopped unexpectedly", detail: "Try again, or type your question.", reference: null, kind: "unknown", code: null },
      });
    };

    // Level meter from the real microphone signal (local only).
    try {
      const audio = new AudioContext();
      const analyser = audio.createAnalyser();
      analyser.fftSize = 512;
      audio.createMediaStreamSource(stream).connect(analyser);
      current.audio = audio;
      const samples = new Uint8Array(analyser.fftSize);
      let lastPaint = 0;
      const tick = (time: number) => {
        analyser.getByteTimeDomainData(samples);
        if (time - lastPaint > 100) {
          let sum = 0;
          for (const sample of samples) sum += ((sample - 128) / 128) ** 2;
          setLevel(Math.min(1, Math.sqrt(sum / samples.length) * 3));
          lastPaint = time;
        }
        current.frame = requestAnimationFrame(tick);
      };
      current.frame = requestAnimationFrame(tick);
    } catch {
      // The meter is optional; recording continues without it.
    }

    const started = performance.now();
    recorder.start(250);
    setState({ step: "recording", elapsed: 0 });
    current.timer = setInterval(() => {
      const elapsed = performance.now() - started;
      if (elapsed >= MAX_MS && recorder.state === "recording") recorder.stop();
      else setState({ step: "recording", elapsed });
    }, 250);
  }

  return {
    state,
    level,
    start: () => void start(),
    /** Finish recording and transcribe for review (never sends the question). */
    stop: () => {
      if (session.current?.recorder?.state === "recording") session.current.recorder.stop();
    },
    /** Cancel at any non-final step; nothing is kept. */
    cancel: () => {
      const current = session.current;
      if (current) {
        current.cancelled = true;
        current.discard = true;
        current.transcribe?.abort();
        if (current.recorder?.state === "recording") current.recorder.stop();
        else release();
      }
      setState({ step: "idle" });
    },
    reset: () => setState({ step: "idle" }),
  };
}
