// Records changed in this tab (an entry saved or undone from quick add): screens that hold
// totals or lists reload. Memory only, like session-events; no record data passes through here.
const listeners = new Set<() => void>();

export function onRecordsChanged(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function emitRecordsChanged() {
  for (const listener of [...listeners]) listener();
}
