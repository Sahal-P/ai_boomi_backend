"use client";

import { useEffect, useRef, useState } from "react";
import { speechFor, type Answer } from "@/lib/api/assistant";
import { isAbort } from "@/lib/api/http";
import { describeProblem, type Problem } from "@/lib/messages";

export type Playback =
  | { step: "idle"; turnId: string | null }
  | { step: "preparing"; turnId: string }
  | { step: "playing"; turnId: string }
  | { step: "ready"; turnId: string }
  | { step: "failed"; turnId: string; problem: Problem };

const playbackProblem: Problem = {
  title: "The audio couldn't be played",
  detail: "Your text answer is still here. Try playing it again.",
  reference: null,
  kind: "unknown",
  code: null,
};

// Imperative media-element helpers live outside the hook so React state stays immutable.
function createPlayer(onEnded: () => void, onError: () => void): HTMLAudioElement {
  const node = new Audio();
  node.preload = "auto";
  node.addEventListener("ended", onEnded);
  node.addEventListener("error", onError);
  return node;
}

function load(node: HTMLAudioElement, url: string) {
  node.src = url;
}

function halt(node: HTMLAudioElement | null) {
  if (!node) return;
  node.pause();
  node.currentTime = 0;
}

/**
 * Prepare-and-play under the person's tap. If the browser blocks playback after a slow
 * preparation, the audio waits behind an explicit Play. The text answer is never affected.
 */
export function useSpeech() {
  const [playback, setPlayback] = useState<Playback>({ step: "idle", turnId: null });
  const player = useRef<HTMLAudioElement | null>(null);
  const playing = useRef<string | null>(null);
  const prepared = useRef<{ turnId: string; url: string } | null>(null);
  const control = useRef<AbortController | null>(null);

  useEffect(
    () => () => {
      control.current?.abort();
      halt(player.current);
      if (prepared.current) URL.revokeObjectURL(prepared.current.url);
    },
    [],
  );

  function element() {
    if (!player.current) {
      player.current = createPlayer(
        () => setPlayback({ step: "idle", turnId: playing.current }),
        () => {
          const turnId = playing.current;
          if (turnId) setPlayback({ step: "failed", turnId, problem: playbackProblem });
        },
      );
    }
    return player.current;
  }

  async function start(turnId: string) {
    playing.current = turnId;
    try {
      await element().play();
      setPlayback({ step: "playing", turnId });
    } catch (error) {
      if (error instanceof DOMException && error.name === "NotAllowedError") {
        // Autoplay rules expired the tap during preparation: wait for an explicit Play.
        setPlayback({ step: "ready", turnId });
      } else if (!(error instanceof DOMException && error.name === "AbortError")) {
        setPlayback({ step: "failed", turnId, problem: playbackProblem });
      }
    }
  }

  async function play(turnId: string, answer: Answer) {
    halt(player.current);
    if (prepared.current?.turnId === turnId) {
      await start(turnId);
      return;
    }
    control.current?.abort();
    const controller = new AbortController();
    control.current = controller;
    setPlayback({ step: "preparing", turnId });
    try {
      const blob = await speechFor(answer, controller.signal);
      if (controller.signal.aborted) return;
      if (prepared.current) URL.revokeObjectURL(prepared.current.url);
      const url = URL.createObjectURL(blob);
      prepared.current = { turnId, url };
      load(element(), url);
      await start(turnId);
    } catch (error) {
      if (isAbort(error) || controller.signal.aborted) {
        setPlayback({ step: "idle", turnId });
        return;
      }
      setPlayback({
        step: "failed",
        turnId,
        problem: describeProblem(error, "Audio isn't available for this answer"),
      });
    } finally {
      if (control.current === controller) control.current = null;
    }
  }

  return {
    playback,
    play: (turnId: string, answer: Answer) => void play(turnId, answer),
    resume: (turnId: string) => void start(turnId),
    stop: () => {
      control.current?.abort();
      halt(player.current);
      setPlayback({ step: "idle", turnId: null });
    },
  };
}
