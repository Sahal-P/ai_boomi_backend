// Task names used in sign-in return messages; page titles live in each route's metadata.
const destinations: Record<string, string> = {
  "/dashboard": "Home",
  "/transactions": "Transactions",
  "/review": "Review",
  "/reports": "Reports",
  "/assistant": "Ask FinBoy",
  "/sources": "Sources",
  "/connect": "Sources",
  "/privacy": "Privacy & data",
};

export function destinationTitle(path: string): string | null {
  const [pathname = "", search = ""] = path.split("?");
  if (pathname.startsWith("/import/")) return "your import results";
  if (new URLSearchParams(search).has("selected")) return "the record you opened";
  return destinations[pathname] ?? null;
}
