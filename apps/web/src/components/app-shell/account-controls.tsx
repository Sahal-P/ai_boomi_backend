"use client";

import { CircleUserRound, Keyboard, LogOut, ShieldCheck } from "lucide-react";
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

/** API reachability only. Data freshness is shown separately on Overview and Sources. */
export function ServiceStatus({ className }: { className?: string }) {
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

/** Desktop sidebar footer: household identity, service status and account actions. */
export function AccountPanel() {
  const { required, household } = useHouseholdAccess();
  const signOut = useGuardedSignOut();
  return (
    <div className="mt-4 space-y-3 border-t border-white/70 px-2 pt-4">
      <div>
        <p className="text-sm font-semibold text-ink">Your household</p>
        <p className="text-xs break-words text-ink-soft">{householdLine(household)}</p>
      </div>
      <ServiceStatus />
      <div className="flex flex-wrap gap-1">
        <Button variant="ghost" size="sm" className="h-11 px-3" onClick={openKeyboardHelp}>
          <Keyboard aria-hidden="true" /> Shortcuts
        </Button>
        {required && (
          <Button
            variant="ghost"
            size="sm"
            className="h-11 px-3"
            disabled={signOut.busy}
            onClick={signOut.request}
          >
            <LogOut aria-hidden="true" /> {signOut.busy ? "Signing out…" : "Sign out"}
          </Button>
        )}
      </div>
      {signOut.problem && (
        <p role="alert" className="text-xs text-destructive">
          {signOut.problem.title}. {signOut.problem.detail}
        </p>
      )}
      <SignOutConfirm state={signOut} />
    </div>
  );
}

/** Phone header account menu; keeps sign-out out of the content area. */
export function AccountMenu() {
  const { required, household } = useHouseholdAccess();
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
          <DropdownMenuLabel className="px-2 py-1.5">
            <span className="block text-sm font-semibold text-ink">Your household</span>
            <span className="block text-xs font-normal break-words text-ink-soft">
              {householdLine(household)}
            </span>
            <ServiceStatus className="mt-1 font-normal" />
          </DropdownMenuLabel>
          <DropdownMenuSeparator />
          <DropdownMenuItem asChild className="min-h-11 px-2">
            <GuardedLink href="/privacy">
              <ShieldCheck aria-hidden="true" /> Privacy &amp; data
            </GuardedLink>
          </DropdownMenuItem>
          <DropdownMenuItem className="min-h-11 px-2" onSelect={openKeyboardHelp}>
            <Keyboard aria-hidden="true" /> Keyboard shortcuts
          </DropdownMenuItem>
          {required && (
            <DropdownMenuItem
              className="min-h-11 px-2"
              disabled={signOut.busy}
              onSelect={signOut.request}
            >
              <LogOut aria-hidden="true" /> {signOut.busy ? "Signing out…" : "Sign out"}
            </DropdownMenuItem>
          )}
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
