"use client";
import { useEffect, useRef, useState } from "react";

export function useVoiceRecorder() {
  const [recording, setRecording] = useState(false);
  const [requesting, setRequesting] = useState(false);
  const [blob, setBlob] = useState<Blob | null>(null);
  const [error, setError] = useState<string | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const active = useRef(true);
  const pending = useRef(false);
  function stop() {
    if (timer.current) clearTimeout(timer.current);
    if (recorder.current?.state === "recording") recorder.current.stop();
    stream.current?.getTracks().forEach((track) => track.stop());
  }
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
      if (timer.current) clearTimeout(timer.current);
      if (recorder.current?.state === "recording") recorder.current.stop();
      stream.current?.getTracks().forEach((track) => track.stop());
    };
  }, []);
  async function start() {
    if (pending.current || recording) return;
    pending.current = true;
    setRequesting(true);
    setError(null);
    setBlob(null);
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setError(
        "Recording is unavailable in this browser. Type your question instead.",
      );
      setRequesting(false);
      pending.current = false;
      return;
    }
    try {
      const input = await navigator.mediaDevices.getUserMedia({ audio: true });
      if (!active.current) {
        input.getTracks().forEach((track) => track.stop());
        return;
      }
      stream.current = input;
      const chunks: Blob[] = [];
      let size = 0;
      let exceeded = false;
      const options = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? { mimeType: "audio/webm;codecs=opus" }
        : undefined;
      const instance = new MediaRecorder(input, options);
      recorder.current = instance;
      instance.ondataavailable = (event) => {
        size += event.data.size;
        if (size > 3 * 1024 * 1024) {
          exceeded = true;
          stop();
        } else chunks.push(event.data);
      };
      instance.onstop = () => {
        input.getTracks().forEach((track) => track.stop());
        if (timer.current) clearTimeout(timer.current);
        if (!active.current) return;
        setRecording(false);
        if (exceeded)
          setError(
            "Recording was too large. Try a shorter question, up to 30 seconds.",
          );
        else {
          const result = new Blob(chunks, {
            type: instance.mimeType || "audio/webm",
          });
          if (result.size) setBlob(result);
          else
            setError(
              "No audio was captured. You can type your question instead.",
            );
        }
      };
      instance.onerror = () => {
        stop();
        if (active.current)
          setError("Recording stopped unexpectedly. Try typing your question.");
      };
      instance.start(250);
      setRecording(true);
      timer.current = setTimeout(stop, 29_000);
    } catch {
      if (active.current) {
        setRecording(false);
        setError(
          "Microphone access was denied or unavailable. Allow it in browser settings, or type your question.",
        );
      }
      stream.current?.getTracks().forEach((track) => track.stop());
    } finally {
      pending.current = false;
      if (active.current) setRequesting(false);
    }
  }
  return { recording, requesting, blob, error, start, stop };
}
