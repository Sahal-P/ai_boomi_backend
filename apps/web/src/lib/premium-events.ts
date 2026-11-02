// "This needs Premium": raised by any API call answered `premium_required`, so the app shell can
// open the upgrade sheet wherever the person was. Memory only.
const listeners = new Set<() => void>();

export function onPremiumRequired(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function emitPremiumRequired() {
  for (const listener of [...listeners]) listener();
}
