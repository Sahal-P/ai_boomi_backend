"use client";
import { useEffect, useRef, useState } from "react";
import {
  askQuestion,
  speechFor,
  transcribeAudio,
  type Answer,
  type DisplayStyle,
} from "@/lib/api/assistant";
import { useVoiceRecorder } from "./use-voice-recorder";

export function useAssistant() {
  const [question, setQuestion] = useState("");
  const [style, setStyle] = useState<DisplayStyle>("auto");
  const [answer, setAnswer] = useState<Answer | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [voiceError, setVoiceError] = useState<string | null>(null);
  const control = useRef<AbortController | null>(null);
  const speechControl = useRef<AbortController | null>(null);
  const audioRef = useRef<string | null>(null);
  const inFlight = useRef(false);
  const speechFlight = useRef(false);
  const recording = useVoiceRecorder();
  useEffect(
    () => () => {
      control.current?.abort();
      speechControl.current?.abort();
      if (audioRef.current) URL.revokeObjectURL(audioRef.current);
    },
    [],
  );
  useEffect(() => {
    const blob = recording.blob;
    if (!blob) return;
    const controller = new AbortController();
    void (async () => {
      setTranscribing(true);
      setVoiceError(null);
      try {
        const result = await transcribeAudio(blob, controller.signal);
        if (controller.signal.aborted) return;
        setQuestion(result.transcript);
        setNotice(
          `Transcript ready (${result.detected_language}). Check it, then ask your question.`,
        );
      } catch {
        if (!controller.signal.aborted)
          setVoiceError(
            "Could not transcribe that recording. Try a shorter recording or type your question.",
          );
      } finally {
        if (!controller.signal.aborted) setTranscribing(false);
      }
    })();
    return () => controller.abort();
  }, [recording.blob]);
  async function ask(text = question) {
    if (!text.trim() || inFlight.current) return;
    inFlight.current = true;
    control.current?.abort();
    const controller = new AbortController();
    control.current = controller;
    speechControl.current?.abort();
    setBusy(true);
    setError(null);
    setAnswer(null);
    setAudioUrl(null);
    setVoiceError(null);
    setSpeaking(false);
    if (audioRef.current) {
      URL.revokeObjectURL(audioRef.current);
      audioRef.current = null;
    }
    try {
      const result = await askQuestion(text.trim(), style, controller.signal);
      if (!controller.signal.aborted) setAnswer(result);
    } catch {
      if (!controller.signal.aborted)
        setError(
          "FinBoy could not answer just now. Check the API connection and try again.",
        );
    } finally {
      inFlight.current = false;
      if (!controller.signal.aborted) setBusy(false);
    }
  }
  async function listen() {
    if (!answer || speechFlight.current) return;
    speechFlight.current = true;
    const controller = new AbortController();
    speechControl.current = controller;
    setSpeaking(true);
    setVoiceError(null);
    try {
      const audio = await speechFor(answer, controller.signal);
      if (controller.signal.aborted) return;
      if (audioRef.current) URL.revokeObjectURL(audioRef.current);
      const url = URL.createObjectURL(audio);
      audioRef.current = url;
      setAudioUrl(url);
    } catch {
      if (!controller.signal.aborted)
        setVoiceError(
          "Audio is unavailable right now. Your text answer is still available.",
        );
    } finally {
      speechFlight.current = false;
      if (!controller.signal.aborted) setSpeaking(false);
    }
  }
  return {
    question,
    setQuestion,
    style,
    setStyle,
    answer,
    error,
    busy,
    transcribing,
    speaking,
    audioUrl,
    notice,
    voiceError,
    recording,
    ask,
    listen,
  };
}
