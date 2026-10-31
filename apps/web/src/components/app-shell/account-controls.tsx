"use client";

import { ChevronsUpDown, CircleUserRound, Inbox, Keyboard, LogOut, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { useHouseholdAccess } from "@/components/app-shell/household-context";
import { GuardedLink } from "@/components/app-shell/guarded-link";
import { openKeyboardHelp } from "@/components/app-shell/keyboard-help";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useHealth } from "@/hooks/use-health";
import type { Household } from "@/lib/api/auth";
import { useSignOut } from "@/hooks/use-household";
import { discardUnsavedWork, hasUnsavedWork } from "@/lib/unsaved-work";
import { cn } from "@/lib/utils";

/** How this household signs in, masked: "WhatsApp •••• 4821 · Google s***@***.com". */
export function householdLine(household: Household | null): string {
  if (!household) return "Private records";
  const ways = [
    household.whatsapp && household.whatsapp !== "linked" ? `WhatsApp ${household.whatsapp}` : null,
    household.whatsapp === "linked" ? "WhatsApp" : null,
    household.google ? `Google ${household.google}` : null,
  ].filter(Boolean);
  if (ways.length) return ways.join(" · ");
  return household.owner ? "Owner · private records" : "Private records";
}

/** API reachability only. Data freshness is shown on Sources. */
export function ServiceStatus({ className }: { className?: string | undefined }) {
  const { connection } = useHealth();
  const label =
    connection.state === "connected"
      ? "Service available"
      : connection.state === "checking"
        ? "Checking service…"
        : connection.state === "degraded"
          ? "Service degraded — records unavailable"
          : "Service unreachable";
  return (
    <p className={cn("flex items-center gap-2 text-xs font-medium text-ink-soft", className)}>
      <span
        aria-hidden="true"
        className={cn(
          "size-2 shrink-0 rounded-full",
          connection.state === "connected"
            ? "bg-positive"
            : connection.state === "checking"
              ? "bg-ink-subtle motion-safe:animate-pulse"
              : "bg-warning",
        )}
      />
      {label}
    </p>
  );
}

function useGuardedSignOut() {
  const action = useSignOut();
  const [confirming, setConfirming] = useState(false);
  return {
    ...action,
    confirming,
    setConfirming,
    request: () => {
      if (hasUnsavedWork()) setConfirming(true);
      else void action.signOut();
    },
    confirm: () => {
      discardUnsavedWork();
      setConfirming(false);
      void action.signOut();
    },
  };
}

function SignOutConfirm({ state }: { state: ReturnType<typeof useGuardedSignOut> }) {
  return (
    <AlertDialog open={state.confirming} onOpenChange={state.setConfirming}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Sign out with unsaved changes?</AlertDialogTitle>
          <AlertDialogDescription>
            Your edits on this page haven&apos;t been saved. Signing out discards them.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Keep editing</AlertDialogCancel>
          <AlertDialogAction variant="destructive" onClick={state.confirm}>
            Discard and sign out
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}

/** Sources, Privacy & data, shortcuts and sign-out: the same menu on phones and desktop. */
function AccountItems({ signOut }: { signOut: ReturnType<typeof useGuardedSignOut> }) {
  const { required, household } = useHouseholdAccess();
  return (
    <>
      <DropdownMenuLabel className="px-2 py-1.5">
        <span className="block text-sm font-semibold text-ink">Your household</span>
        <span className="block text-xs font-normal break-words text-ink-soft">
          {householdLine(household)}
        </span>
        <ServiceStatus className="mt-1 font-normal" />
      </DropdownMenuLabel>
      <DropdownMenuSeparator />
      <DropdownMenuItem asChild className="min-h-11 px-2">
        <GuardedLink href="/sources">
          <Inbox aria-hidden="true" /> Sources
        </GuardedLink>
      </DropdownMenuItem>
      <DropdownMenuItem asChild className="min-h-11 px-2">
        <GuardedLink href="/privacy">
          <ShieldCheck aria-hidden="true" /> Privacy &amp; data
        </GuardedLink>
      </DropdownMenuItem>
      <DropdownMenuItem className="min-h-11 px-2" onSelect={openKeyboardHelp}>
        <Keyboard aria-hidden="true" /> Keyboard shortcuts
      </DropdownMenuItem>
      {required && (
        <>
          <DropdownMenuSeparator />
          <DropdownMenuItem className="min-h-11 px-2" disabled={signOut.busy} onSelect={signOut.request}>
            <LogOut aria-hidden="true" /> {signOut.busy ? "Signing out…" : "Sign out"}
          </DropdownMenuItem>
        </>
      )}
    </>
  );
}

/** The sidebar mentions the service only when it is degraded or unreachable. */
function ServiceProblem({ className }: { className?: string | undefined }) {
  const { connection } = useHealth();
  if (connection.state === "connected" || connection.state === "checking") return null;
  return <ServiceStatus className={className} />;
}

/** Desktop sidebar footer: one account button that opens the account menu. */
export function AccountPanel() {
  const { household } = useHouseholdAccess();
  const signOut = useGuardedSignOut();
  return (
    <div className="mt-4 space-y-2 border-t border-white/70 pt-3">
      <ServiceProblem className="px-2" />
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
              <span className="block text-sm font-semibold text-ink">Your household</span>
              <span className="block truncate text-xs text-ink-soft">{householdLine(household)}</span>
            </span>
            <ChevronsUpDown className="size-4 shrink-0 text-ink-soft" aria-hidden="true" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent side="top" align="start" className="w-[232px] rounded-2xl p-2">
          <AccountItems signOut={signOut} />
        </DropdownMenuContent>
      </DropdownMenu>
      {signOut.problem && (
        <p role="alert" className="px-2 text-xs text-destructive">
          {signOut.problem.title}. {signOut.problem.detail}
        </p>
      )}
      <SignOutConfirm state={signOut} />
    </div>
  );
}

/** Phone header account menu; keeps Sources, Privacy & data and sign-out out of the tab bar. */
export function AccountMenu() {
  const signOut = useGuardedSignOut();
  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="icon"
            aria-label="Account and settings"
            className="bg-white shadow-hairline hover:bg-white aria-expanded:bg-white"
          >
            <CircleUserRound className="size-5" aria-hidden="true" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-64 rounded-2xl p-2">
          <AccountItems signOut={signOut} />
        </DropdownMenuContent>
      </DropdownMenu>
      {signOut.problem && (
        <p role="alert" className="sr-only">
          {signOut.problem.title}. {signOut.problem.detail}
        </p>
      )}
      <SignOutConfirm state={signOut} />
    </>
  );
}
