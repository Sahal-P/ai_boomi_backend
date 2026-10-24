// Household session signals shared by API clients and the app shell. Memory only:
// no password, cookie or session value ever passes through here.
type SessionEvent = "expired" | "restored";
const listeners: Record<SessionEvent, Set<() => void>> = {
  expired: new Set(),
  restored: new Set(),
};

export function onSessionEvent(event: SessionEvent, listener: () => void) {
  listeners[event].add(listener);
  return () => {
    listeners[event].delete(listener);
  };
}

export function emitSessionEvent(event: SessionEvent) {
  for (const listener of [...listeners[event]]) listener();
}
