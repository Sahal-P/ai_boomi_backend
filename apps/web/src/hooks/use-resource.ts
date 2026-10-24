"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, isAbort } from "@/lib/api/http";
import { onSessionEvent } from "@/lib/session-events";

export type ResourceStatus = "idle" | "loading" | "ready" | "refreshing" | "error";

export type Resource<T> = {
  data: T | null;
  /** The data belongs to an earlier key (for example the previous filter). */
  stale: boolean;
  error: unknown;
  status: ResourceStatus;
  loadedAt: number | null;
  reload: () => void;
  /** Replace data with a fresher server response (for example a mutation result). */
  replace: (data: T) => void;
};

type State<T> = {
  data: T | null;
  dataKey: string | null;
  error: unknown;
  settled: string | null;
  loadedAt: number | null;
};

const retryAfter = (error: unknown) =>
  error instanceof ApiError && ["session", "offline", "network", "timeout"].includes(error.kind);

/**
 * Loads one independent piece of data. The last successful result stays available while a
 * newer request is pending or after it fails, and the screen decides how to label it.
 * `key === null` means "not requested yet".
 */
export function useResource<T>(
  key: string | null,
  load: (signal: AbortSignal) => Promise<T>,
): Resource<T> {
  const loader = useRef(load);
  useEffect(() => {
    loader.current = load;
  });
  const [version, setVersion] = useState(0);
  const [state, setState] = useState<State<T>>({
    data: null,
    dataKey: null,
    error: null,
    settled: null,
    loadedAt: null,
  });
  const request = key === null ? null : `${key}#${version}`;

  useEffect(() => {
    if (request === null) return;
    const controller = new AbortController();
    loader.current(controller.signal).then(
      (data) => {
        if (controller.signal.aborted) return;
        setState({ data, dataKey: key, error: null, settled: request, loadedAt: Date.now() });
      },
      (error: unknown) => {
        if (controller.signal.aborted || isAbort(error)) return;
        setState((previous) => ({ ...previous, error, settled: request }));
      },
    );
    return () => controller.abort();
  }, [request, key]);

  const reload = useCallback(() => setVersion((value) => value + 1), []);
  const replace = useCallback(
    (data: T) =>
      setState((previous) => ({
        ...previous,
        data,
        dataKey: key,
        error: null,
        loadedAt: Date.now(),
      })),
    [key],
  );

  // Recover automatically when the session is restored or the device comes back online.
  const failed = state.settled === request && state.error !== null && retryAfter(state.error);
  useEffect(() => {
    if (!failed) return;
    const stop = onSessionEvent("restored", reload);
    window.addEventListener("online", reload);
    return () => {
      stop();
      window.removeEventListener("online", reload);
    };
  }, [failed, reload]);

  const pending = request !== null && state.settled !== request;
  const status: ResourceStatus =
    request === null
      ? "idle"
      : pending
        ? state.data === null
          ? "loading"
          : "refreshing"
        : state.error
          ? "error"
          : "ready";
  return {
    data: state.data,
    stale: state.data !== null && state.dataKey !== key,
    error: status === "error" ? state.error : null,
    status,
    loadedAt: state.loadedAt,
    reload,
    replace,
  };
}
