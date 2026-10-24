// Single-key shortcut preference. Stored locally because it is a UI setting, not personal data.
const KEY = "finboy:shortcuts";
const listeners = new Set<() => void>();

export function shortcutsEnabled(): boolean {
  try {
    return window.localStorage.getItem(KEY) !== "off";
  } catch {
    return true;
  }
}

export function setShortcutsEnabled(enabled: boolean) {
  try {
    if (enabled) window.localStorage.removeItem(KEY);
    else window.localStorage.setItem(KEY, "off");
  } catch {
    // Storage can be unavailable (private mode); the session default still applies.
  }
  listeners.forEach((listener) => listener());
}

export function subscribeShortcuts(listener: () => void) {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

/** True when a key press belongs to text entry or another control, not a shortcut. */
export function typingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable) return true;
  return ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName);
}
