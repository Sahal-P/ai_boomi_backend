import { redirect } from "next/navigation";

// Old Connect links and the registered Gmail callback (`/connect?error=…`) land on Sources.
export default async function ConnectPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string | string[] }>;
}) {
  const { error } = await searchParams;
  const code = typeof error === "string" && /^[a-z_]{1,40}$/.test(error) ? error : null;
  redirect(code ? `/sources?error=${code}` : "/sources");
}
