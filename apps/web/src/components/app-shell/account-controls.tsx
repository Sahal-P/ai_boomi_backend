"use client";

import { ChevronsUpDown, CircleUserRound, Inbox, Keyboard, LogOut, ShieldCheck, Sparkles } from "lucide-react";
import { useState } from "react";
import { useHouseholdAccess } from "@/components/app-shell/household-context";
import { GuardedLink } from "@/components/app-shell/guarded-link";
import { openKeyboardHelp } from "@/components/app-shell/keyboard-help";
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
  DropdownMenuRadioGroup,
  DropdownMenuRadioItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { setGlassLook, useGlassLook } from "@/components/liquid-glass/glass-store";
import { useLiquidGlass } from "@/components/liquid-glass/use-liquid-glass";
import { useHealth } from "@/hooks/use-health";
import type { Household } from "@/lib/api/auth";
import { useSignOut } from "@/hooks/use-household";
import { isGlassLook } from "@/lib/liquid-glass/tier";
import { statusLine } from "@/lib/plan";
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

/**
 * Clear · Tinted, as iOS 26.1's Liquid Glass setting: Tinted makes every glass surface frostier and
 * more opaque. Applies at once (the menu stays open to show it) and is remembered on this device.
 */
function GlassLookChoice() {
  const look = useGlassLook();
  return (
    <>
      <DropdownMenuLabel className="px-2 pt-1.5 pb-0.5 text-xs font-medium text-ink-soft">Glass</DropdownMenuLabel>
      <DropdownMenuRadioGroup
        value={look}
        onValueChange={(value) => {
          if (isGlassLook(value)) setGlassLook(value);
        }}
      >
        <DropdownMenuRadioItem value="clear" className="min-h-11 px-2" onSelect={(event) => event.preventDefault()}>
          <span className="min-w-0">
            <span className="block">Clear</span>
            <span className="block text-xs text-ink-soft">See more of what&apos;s behind</span>
          </span>
        </DropdownMenuRadioItem>
        <DropdownMenuRadioItem value="tinted" className="min-h-11 px-2" onSelect={(event) => event.preventDefault()}>
          <span className="min-w-0">
            <span className="block">Tinted</span>
            <span className="block text-xs text-ink-soft">Frostier, easier to read</span>
          </span>
        </DropdownMenuRadioItem>
      </DropdownMenuRadioGroup>
    </>
  );
}

/** Sources, Privacy & data, shortcuts, the glass look and sign-out: one menu on phones and desktop. */
function AccountItems({ signOut }: { signOut: ReturnType<typeof useGuardedSignOut> }) {
  const { required, household, plan } = useHouseholdAccess();
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
      {plan && (
        <DropdownMenuItem asChild className="min-h-11 px-2">
          <GuardedLink href="/plan">
            <Sparkles aria-hidden="true" />
            <span className="min-w-0">
              <span className="block">Plan</span>
              <span className="block text-xs text-ink-soft">{statusLine(plan)}</span>
            </span>
          </GuardedLink>
        </DropdownMenuItem>
      )}
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
      <DropdownMenuSeparator />
      <GlassLookChoice />
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
            className="flex w-full items-center gap-3 rounded-[20px] px-2 py-2 text-left transition-colors hover:bg-white/45 aria-expanded:bg-white/55"
          >
            <span className="lg-static grid size-9 shrink-0 place-items-center rounded-full [--lg-static-tint:0.85]">
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

/** Phone account button: a small floating glass circle over the top scroll edge. Its menu keeps
 *  Sources, Privacy & data, the glass look and sign-out out of the tab bar. */
export function AccountMenu() {
  const signOut = useGuardedSignOut();
  const { attach, filter } = useLiquidGlass<HTMLButtonElement>({ bezel: 12, thickness: 14 });
  return (
    <>
      {filter}
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            ref={attach}
            type="button"
            aria-label="Account and settings"
            data-glass-press=""
            className="lg grid size-11 place-items-center rounded-full text-ink outline-none focus-visible:ring-3 focus-visible:ring-ring/50 aria-expanded:[--lg-tint:0.7]"
          >
            <CircleUserRound className="size-5" aria-hidden="true" />
          </button>
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
