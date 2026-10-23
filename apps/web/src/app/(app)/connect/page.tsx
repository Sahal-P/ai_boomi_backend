import { ConnectClient } from "./connect-client";

export default async function ConnectPage({ searchParams }: {
  searchParams: Promise<{ error?: string | string[] }>;
}) {
  const { error } = await searchParams;
  return <ConnectClient errorCode={typeof error === "string" ? error : undefined} />;
}
