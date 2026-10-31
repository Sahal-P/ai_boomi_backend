"use client";

import { useEffect, useRef } from "react";
import { onRecordsChanged } from "@/lib/record-events";

/** Runs `listener` whenever records change elsewhere in this tab, such as from quick add. */
export function useRecordsChanged(listener: () => void) {
  const latest = useRef(listener);
  useEffect(() => {
    latest.current = listener;
  });
  useEffect(() => onRecordsChanged(() => latest.current()), []);
}
