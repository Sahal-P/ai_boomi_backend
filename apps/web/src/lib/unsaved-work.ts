// In-memory registry of unsaved drafts. Draft values never go to browser storage; this only
// records that some form is dirty so navigation can ask before discarding it.
const dirty = new Set<string>();
const listeners = new Set<() => void>();
let pendingHref: string | null = null;

function notify() {
  for (const listener of [...listeners]) listener();
}

export function setUnsaved(id: string, isDirty: boolean) {
  const had = dirty.has(id);
  if (isDirty) dirty.add(id);
  else dirty.delete(id);
  if (had !== isDirty) notify();
}

export function hasUnsavedWork() {
  return dirty.size > 0;
}

export function discardUnsavedWork() {
  dirty.clear();
  pendingHref = null;
  notify();
}

/** Ask to leave for an in-app destination; the confirmation dialog reads it. */
export function requestLeave(href: string) {
  pendingHref = href;
  notify();
}

export function cancelLeave() {
  pendingHref = null;
  notify();
}

export function leaveRequest() {
  return pendingHref;
}

export function subscribeUnsaved(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}
