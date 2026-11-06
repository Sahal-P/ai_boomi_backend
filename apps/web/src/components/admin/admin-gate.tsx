"use client";

import { LoaderCircle } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, type ReactNode } from "react";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { useAdminSession } from "@/hooks/use-admin";

export const PASSWORD_PAGE = "/admin/password";

type AdminAccess = { email: string; mustChangePassword: boolean; passwordChanged: () => void };
const AdminContext = createContext<AdminAccess>({ email: "", mustChangePassword: false, passwordChanged: () => {} });

/** The signed-in admin. Only steers the screens: the API enforces every rule. */
export function useAdminAccess() {
  return useContext(AdminContext);
}

/** Shows the console only to a signed-in admin; a temporary password opens the password page only. */
export function AdminGate({ children }: { children: ReactNode }) {
  const { state, session, problem, passwordChanged, retry } = useAdminSession();
  const pathname = usePathname();
  const router = useRouter();
  const detour = Boolean(session?.must_change_password) && pathname !== PASSWORD_PAGE;
  useEffect(() => {
    if (detour) router.replace(PASSWORD_PAGE);
  }, [detour, router]);

  if (state !== "ready" || !session || detour) {
    return (
      <main className="bg-field bg-wallpaper grid min-h-dvh place-items-center p-6">
        {state === "unavailable" && problem ? (
          <div className="w-full max-w-md">
            <ProblemNotice problem={problem} onRetry={retry} />
          </div>
        ) : (
          <p role="status" className="surface flex items-center gap-3 rounded-3xl p-6 text-sm">
            <LoaderCircle className="size-4 motion-safe:animate-spin" aria-hidden="true" />
            Checking admin access…
          </p>
        )}
      </main>
    );
  }
  return (
    <AdminContext value={{ email: session.email, mustChangePassword: session.must_change_password, passwordChanged }}>
      {children}
    </AdminContext>
  );
}
