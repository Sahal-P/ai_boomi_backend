import type { Metadata } from "next";
import { AdminLogin } from "@/components/admin/admin-login";
import { safeAdminReturnPath } from "@/lib/api/admin";

export const metadata: Metadata = { title: "Sign in" };

export default async function AdminLoginPage({
  searchParams,
}: {
  searchParams: Promise<{ next?: string | string[] }>;
}) {
  const { next } = await searchParams;
  return <AdminLogin next={safeAdminReturnPath(typeof next === "string" ? next : null)} />;
}
