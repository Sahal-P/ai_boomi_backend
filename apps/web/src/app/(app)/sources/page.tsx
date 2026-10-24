import type { Metadata } from "next";
import { SourcesScreen } from "@/components/sources/sources-screen";

export const metadata: Metadata = { title: "Sources" };

export default async function SourcesPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string | string[]; intent?: string | string[] }>;
}) {
  const { error, intent } = await searchParams;
  return (
    <SourcesScreen
      errorCode={typeof error === "string" && /^[a-z_]{1,40}$/.test(error) ? error : null}
      intent={intent === "gmail" ? "gmail" : null}
    />
  );
}
