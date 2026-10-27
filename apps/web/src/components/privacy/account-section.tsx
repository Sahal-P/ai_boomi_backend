"use client";

import { LogOut, MessageCircle, Trash2, UserRound } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { householdLine } from "@/components/app-shell/account-controls";
import { useHouseholdAccess } from "@/components/app-shell/household-context";
import { WhatsAppSignIn } from "@/components/app-shell/sign-in-options";
import { ProblemNotice } from "@/components/feedback/problem-notice";
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
import { Button } from "@/components/ui/button";
import { useAction } from "@/hooks/use-action";
import { useGoogleSignIn } from "@/hooks/use-google-sign-in";
import { useWhatsAppSignIn } from "@/hooks/use-whatsapp-sign-in";
import { deleteAccount, signOutEverywhere } from "@/lib/api/auth";

function LinkWhatsApp({ onLinked }: { onLinked: () => void }) {
  const [linking, setLinking] = useState(false);
  const whatsapp = useWhatsAppSignIn({ enabled: linking, purpose: "link", onDone: onLinked });
  if (!linking) {
    return (
      <Button variant="outline" onClick={() => setLinking(true)}>
        <MessageCircle aria-hidden="true" /> Link WhatsApp
      </Button>
    );
  }
  return (
    <div className="rounded-2xl bg-well p-4 ring-1 ring-ink/5">
      <WhatsAppSignIn phase={whatsapp.phase} onOpened={whatsapp.opened} onRestart={whatsapp.restart} purpose="link" />
    </div>
  );
}

function LinkGoogle({ clientId, onLinked }: { clientId: string; onLinked: () => void }) {
  const { container, problem, busy } = useGoogleSignIn({ clientId, link: true, onDone: onLinked });
  return (
    <div className="space-y-2">
      <div ref={container} className="flex min-h-11" aria-busy={busy} />
      {problem && <ProblemNotice problem={problem} />}
    </div>
  );
}

/**
 * How this household signs in, linking a second way, and leaving FinBoy. Deleting is for
 * households that joined by themselves; the owner's household is managed by the operator.
 */
export function AccountSection() {
  const router = useRouter();
  const { household, signIn } = useHouseholdAccess();
  const action = useAction();
  const [confirming, setConfirming] = useState(false);
  if (!household || !signIn) return null;
  const selfServe = household.joined_via !== null;
  // The household's sign-in methods are read once per visit, so reload to show the new one.
  const refresh = () => window.location.reload();
  return (
    <section aria-labelledby="account-title" className="surface rounded-3xl p-5 sm:p-6">
      <h2 id="account-title" className="flex items-center gap-2 text-lg font-semibold">
        <UserRound className="size-5" aria-hidden="true" /> Your sign-in
      </h2>
      <p className="mt-1 text-sm break-words text-ink-soft">{householdLine(household)}</p>
      <div className="mt-4 flex flex-wrap items-start gap-3">
        {!household.whatsapp && signIn.whatsapp && (
          <LinkWhatsApp onLinked={refresh} />
        )}
        {!household.google && signIn.google_client_id && (
          <LinkGoogle
            clientId={signIn.google_client_id}
            onLinked={refresh}
          />
        )}
      </div>
      {selfServe && (
        <div className="mt-5 flex flex-wrap gap-2 border-t border-ink/10 pt-4">
          <Button
            variant="outline"
            disabled={action.busy !== null}
            onClick={() =>
              void action
                .run("everywhere", "You're still signed in", () => signOutEverywhere())
                .then((done) => done && router.replace("/login"))
            }
          >
            <LogOut aria-hidden="true" /> Sign out on every device
          </Button>
          <Button variant="destructive" disabled={action.busy !== null} onClick={() => setConfirming(true)}>
            <Trash2 aria-hidden="true" /> Delete my account
          </Button>
        </div>
      )}
      {action.problem && <ProblemNotice className="mt-3" problem={action.problem} />}
      <AlertDialog open={confirming} onOpenChange={setConfirming}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete your FinBoy account?</AlertDialogTitle>
            <AlertDialogDescription>
              Every record, due, correction and linked sign-in is deleted, Gmail access is revoked,
              and every device is signed out. WhatsApp stops answering this number until it joins
              again. This can&apos;t be undone — export your records first if you want a copy.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Keep my account</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() =>
                void action
                  .run("delete", "Your account wasn't deleted", () => deleteAccount())
                  .then((done) => done && router.replace("/"))
              }
            >
              Delete everything
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}
