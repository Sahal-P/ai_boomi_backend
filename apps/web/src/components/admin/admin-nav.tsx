"use client";

import {
  ChevronsUpDown,
  CircleUserRound,
  CreditCard,
  Ellipsis,
  KeyRound,
  LayoutDashboard,
  LogOut,
  ScrollText,
  Server,
  ShieldCheck,
  UserPlus,
  Users,
} from "lucide-react";
import { motion } from "motion/react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { useAdminAccess } from "@/components/admin/admin-gate";
import { Brand } from "@/components/brand";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useAdminSignOut } from "@/hooks/use-admin";
import { cn } from "@/lib/utils";

export const ADMIN_NAVIGATION = [
  { label: "Overview", href: "/admin", icon: LayoutDashboard },
  { label: "Households", href: "/admin/households", icon: Users },
  { label: "Payments", href: "/admin/payments", icon: CreditCard },
  { label: "Sign-ups", href: "/admin/signups", icon: UserPlus },
  { label: "System", href: "/admin/system", icon: Server },
  { label: "Admins", href: "/admin/admins", icon: ShieldCheck },
  { label: "Audit log", href: "/admin/audit", icon: ScrollText },
] as const;
// Phones keep the daily pages in the tab bar; the rest sit under More.
const TABS = ADMIN_NAVIGATION.slice(0, 3);
const MORE = ADMIN_NAVIGATION.slice(3);

function isActive(pathname: string, href: string) {
  return href === "/admin" ? pathname === "/admin" : pathname === href || pathname.startsWith(`${href}/`);
}

function AdminChip() {
  return <span className="rounded-full bg-ink px-2 py-0.5 text-[11px] font-semibold text-white">Admin</span>;
}

function AccountItems({ signOut }: { signOut: ReturnType<typeof useAdminSignOut> }) {
  const { email } = useAdminAccess();
  return (
    <>
      <DropdownMenuLabel className="px-2 py-1.5">
        <span className="block text-sm font-semibold text-ink">Signed in as</span>
        <span className="block text-xs font-normal break-all text-ink-soft">{email}</span>
      </DropdownMenuLabel>
      <DropdownMenuSeparator />
      <DropdownMenuItem asChild className="min-h-11 px-2">
        <Link href="/admin/password">
          <KeyRound aria-hidden="true" /> Change password
        </Link>
      </DropdownMenuItem>
      <DropdownMenuSeparator />
      <DropdownMenuItem className="min-h-11 px-2" disabled={signOut.busy} onSelect={() => void signOut.signOut()}>
        <LogOut aria-hidden="true" /> {signOut.busy ? "Signing out…" : "Sign out"}
      </DropdownMenuItem>
    </>
  );
}

function SignOutProblem({ signOut, visible }: { signOut: ReturnType<typeof useAdminSignOut>; visible: boolean }) {
  if (!signOut.problem) return null;
  return (
    <p role="alert" className={visible ? "px-2 text-xs text-destructive" : "sr-only"}>
      {signOut.problem.title}. {signOut.problem.detail}
    </p>
  );
}

/** Desktop sidebar footer: who is signed in, password and sign-out. */
function AccountPanel() {
  const { email } = useAdminAccess();
  const signOut = useAdminSignOut();
  return (
    <div className="mt-4 space-y-2 border-t border-white/70 pt-3">
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            className="flex w-full items-center gap-3 rounded-2xl px-2 py-2 text-left transition-colors hover:bg-white/60 aria-expanded:bg-white/70"
          >
            <span className="grid size-9 shrink-0 place-items-center rounded-full bg-white shadow-hairline">
              <CircleUserRound className="size-5" aria-hidden="true" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-sm font-semibold text-ink">Admin account</span>
              <span className="block truncate text-xs text-ink-soft">{email}</span>
            </span>
            <ChevronsUpDown className="size-4 shrink-0 text-ink-soft" aria-hidden="true" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent side="top" align="start" className="w-[232px] rounded-2xl p-2">
          <AccountItems signOut={signOut} />
        </DropdownMenuContent>
      </DropdownMenu>
      <SignOutProblem signOut={signOut} visible />
    </div>
  );
}

function AccountMenu() {
  const signOut = useAdminSignOut();
  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Admin account"
            className="bg-white shadow-hairline hover:bg-white aria-expanded:bg-white"
          >
            <CircleUserRound className="size-5" aria-hidden="true" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-64 rounded-2xl p-2">
          <AccountItems signOut={signOut} />
        </DropdownMenuContent>
      </DropdownMenu>
      <SignOutProblem signOut={signOut} visible={false} />
    </>
  );
}

function TabCell({ active, children }: { active: boolean; children: ReactNode }) {
  return (
    <>
      {active ? (
        <motion.span
          layoutId="admin-tab-active"
          className="absolute inset-0 rounded-full bg-ink shadow-lift"
          transition={{ type: "spring", stiffness: 420, damping: 36 }}
        />
      ) : null}
      {children}
    </>
  );
}

const tabClass = (active: boolean) =>
  cn(
    "relative flex h-12 w-full flex-col items-center justify-center gap-1 rounded-full px-1 text-[11px] leading-none font-semibold whitespace-nowrap",
    active ? "px-2.5 text-white" : "text-ink-soft",
  );

/** The admin console's sidebar (desktop), and a header with a tab pill (phones). */
export function AdminNav() {
  const pathname = usePathname();
  const { mustChangePassword } = useAdminAccess();
  const moreActive = MORE.some(({ href }) => isActive(pathname, href));
  const current = MORE.find(({ href }) => isActive(pathname, href));

  return (
    <>
      <aside className="surface fixed top-3 bottom-3 left-3 z-40 hidden w-[264px] flex-col rounded-3xl p-4 lg:flex">
        <div className="flex items-center gap-2 px-2 pt-1">
          <Brand href="/admin" label="FinBoy admin overview" />
          <AdminChip />
        </div>
        {mustChangePassword ? (
          <p className="mt-7 flex-1 px-2 text-sm leading-relaxed text-ink-soft">
            Choose a new password to open the rest of the panel.
          </p>
        ) : (
          <nav aria-label="Admin navigation" className="mt-7 flex-1">
            <ul className="space-y-1">
              {ADMIN_NAVIGATION.map(({ label, href, icon: Icon }) => {
                const active = isActive(pathname, href);
                return (
                  <li key={href}>
                    <Link
                      href={href}
                      aria-current={active ? "page" : undefined}
                      className={cn(
                        "relative flex h-11 items-center gap-3 rounded-full px-3.5 text-sm font-semibold transition-colors",
                        active ? "text-white" : "text-ink-soft hover:bg-white/60 hover:text-ink",
                      )}
                    >
                      {active ? (
                        <motion.span
                          layoutId="admin-nav-active"
                          className="absolute inset-0 rounded-full bg-ink shadow-lift"
                          transition={{ type: "spring", stiffness: 420, damping: 36 }}
                        />
                      ) : null}
                      <Icon className="relative size-[18px]" aria-hidden="true" />
                      <span className="relative">{label}</span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </nav>
        )}
        <AccountPanel />
      </aside>

      <header className="glass fixed inset-x-3 top-3 z-40 flex h-14 items-center justify-between rounded-full bg-white/[0.9] pr-1.5 pl-4 lg:hidden">
        <div className="flex min-w-0 items-center gap-2">
          <Brand href="/admin" label="FinBoy admin overview" />
          <AdminChip />
        </div>
        <AccountMenu />
      </header>

      {!mustChangePassword && (
        <div className="app-tabbar fixed inset-x-3 bottom-[max(0.75rem,env(safe-area-inset-bottom))] z-40 lg:hidden">
          <nav aria-label="Admin navigation" className="glass rounded-full bg-white/[0.94] p-1.5">
            <ul className="flex">
              {TABS.map(({ label, href, icon: Icon }) => {
                const active = isActive(pathname, href);
                return (
                  <li key={href} className="min-w-11 flex-auto">
                    <Link href={href} aria-current={active ? "page" : undefined} className={tabClass(active)}>
                      <TabCell active={active}>
                        <Icon className="relative size-[18px]" aria-hidden="true" />
                        <span className="relative">{label}</span>
                      </TabCell>
                    </Link>
                  </li>
                );
              })}
              <li className="min-w-11 flex-auto">
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button
                      type="button"
                      aria-label={current ? `More pages, showing ${current.label}` : "More pages"}
                      className={tabClass(moreActive)}
                    >
                      <TabCell active={moreActive}>
                        <Ellipsis className="relative size-[18px]" aria-hidden="true" />
                        <span className="relative">{current ? current.label : "More"}</span>
                      </TabCell>
                    </button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent side="top" align="end" className="w-56 rounded-2xl p-2">
                    {MORE.map(({ label, href, icon: Icon }) => (
                      <DropdownMenuItem key={href} asChild className="min-h-11 px-2">
                        <Link href={href} aria-current={isActive(pathname, href) ? "page" : undefined}>
                          <Icon aria-hidden="true" /> {label}
                        </Link>
                      </DropdownMenuItem>
                    ))}
                  </DropdownMenuContent>
                </DropdownMenu>
              </li>
            </ul>
          </nav>
        </div>
      )}
    </>
  );
}
