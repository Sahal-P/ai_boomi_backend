// Labels for "Where sign-ups came from" in the admin panel (docs/ad-journey-round/contract.md).

/** "4.5 min", "1 h 20 min", "2 d 3 h", or a dash. */
export function span(minutes: number | null): string {
  if (minutes === null) return "—";
  if (minutes < 60) return `${Math.round(minutes * 10) / 10} min`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} h ${Math.round(minutes % 60)} min`;
  return `${Math.floor(hours / 24)} d ${hours % 24} h`;
}

/** What a row's link said: its tags, or why it has none. */
export function sourceLabel(row: {
  source: string | null;
  medium: string | null;
  campaign: string | null;
  direct: boolean;
}): string {
  if (row.direct) return "No visit (shared number, QR code or an old link)";
  const tags = [row.source, row.medium, row.campaign].filter(Boolean);
  return tags.length ? tags.join(" · ") : "No tags";
}
