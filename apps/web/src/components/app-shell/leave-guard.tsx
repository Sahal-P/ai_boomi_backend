"use client";

import { useRouter } from "next/navigation";
import { useEffect, useSyncExternalStore } from "react";
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
  cancelLeave,
  discardUnsavedWork,
  hasUnsavedWork,
  leaveRequest,
  subscribeUnsaved,
} from "@/lib/unsaved-work";

/** Asks before in-app navigation or reload discards a dirty draft. */
export function LeaveGuard() {
  const router = useRouter();
  const href = useSyncExternalStore(subscribeUnsaved, leaveRequest, () => null);
  const dirty = useSyncExternalStore(subscribeUnsaved, hasUnsavedWork, () => false);
  useEffect(() => {
    if (!dirty) return;
    const warn = (event: BeforeUnloadEvent) => event.preventDefault();
    window.addEventListener("beforeunload", warn);
    return () => window.removeEventListener("beforeunload", warn);
  }, [dirty]);
  return (
    <AlertDialog open={href !== null} onOpenChange={(open) => !open && cancelLeave()}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Leave without saving?</AlertDialogTitle>
          <AlertDialogDescription>
            Your edits on this page haven&apos;t been saved. If you leave now they&apos;ll be
            discarded.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Keep editing</AlertDialogCancel>
          <AlertDialogAction
            variant="destructive"
            onClick={() => {
              if (!href) return;
              discardUnsavedWork();
              router.push(href);
            }}
          >
            Discard and leave
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
