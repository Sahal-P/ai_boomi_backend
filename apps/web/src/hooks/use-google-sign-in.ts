"use client";

import { useEffect, useRef, useState } from "react";
import { signInWithGoogle, startGoogle } from "@/lib/api/auth";
import { isAbort } from "@/lib/api/http";
import { describeProblem, type Problem } from "@/lib/messages";

type GoogleIdentity = {
  accounts: {
    id: {
      initialize(config: {
        client_id: string;
        nonce: string;
        callback: (response: { credential?: string }) => void;
        auto_select: boolean;
        cancel_on_tap_outside: boolean;
        context: "signin" | "use";
        ux_mode: "popup";
        itp_support: boolean;
        use_fedcm_for_prompt: boolean;
      }): void;
      renderButton(
        parent: HTMLElement,
        options: {
          type: "standard";
          theme: "outline";
          size: "large";
          text: "continue_with";
          shape: "pill";
          logo_alignment: "left";
          width: number;
        },
      ): void;
      prompt(): void;
      cancel(): void;
    };
  };
};

declare global {
  interface Window {
    google?: GoogleIdentity;
  }
}

const SCRIPT = "https://accounts.google.com/gsi/client";
let loading: Promise<GoogleIdentity> | null = null;

/** Google's sign-in script, loaded only on the sign-in surfaces that need it. */
function loadGoogle(): Promise<GoogleIdentity> {
  if (window.google?.accounts?.id) return Promise.resolve(window.google);
  loading ??= new Promise<GoogleIdentity>((resolve, reject) => {
    const script = document.createElement("script");
    script.src = SCRIPT;
    script.async = true;
    script.onload = () =>
      window.google?.accounts?.id ? resolve(window.google) : reject(new Error("unavailable"));
    script.onerror = () => {
      loading = null;
      script.remove();
      reject(new Error("unavailable"));
    };
    document.head.append(script);
  });
  return loading;
}

/**
 * "Continue with Google" through Google Identity Services. The button is Google's own; the ID
 * token goes once to FinBoy's backend, which checks it against this browser's nonce.
 */
export function useGoogleSignIn({
  clientId,
  link = false,
  onDone,
}: {
  clientId: string | null;
  link?: boolean;
  onDone: (result: "signed_in" | "linked") => void;
}) {
  // A callback ref kept in state: Google's button is drawn once its container exists.
  const [parent, setParent] = useState<HTMLDivElement | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [busy, setBusy] = useState(false);
  const done = useRef(onDone);
  useEffect(() => {
    done.current = onDone;
  });

  useEffect(() => {
    if (!clientId || !parent) return;
    const controller = new AbortController();
    Promise.all([startGoogle(controller.signal), loadGoogle()]).then(
      ([{ nonce }, google]) => {
        if (controller.signal.aborted) return;
        google.accounts.id.initialize({
          client_id: clientId,
          nonce,
          auto_select: false,
          cancel_on_tap_outside: true,
          context: link ? "use" : "signin",
          ux_mode: "popup",
          itp_support: true,
          use_fedcm_for_prompt: true,
          callback: ({ credential }) => {
            if (!credential) return;
            setBusy(true);
            setProblem(null);
            signInWithGoogle(credential, link).then(
              (result) => done.current("linked" in result ? "linked" : "signed_in"),
              (error: unknown) => {
                setBusy(false);
                setProblem(describeProblem(error, link ? "Google wasn't linked" : "You're not signed in yet"));
              },
            );
          },
        });
        google.accounts.id.renderButton(parent, {
          type: "standard",
          theme: "outline",
          size: "large",
          text: "continue_with",
          shape: "pill",
          logo_alignment: "left",
          width: Math.max(200, Math.min(400, Math.round(parent.getBoundingClientRect().width) || 320)),
        });
        // One Tap: returning Android/Chrome visitors can continue with a single tap.
        if (!link) google.accounts.id.prompt();
      },
      (error: unknown) => {
        if (controller.signal.aborted || isAbort(error)) return;
        setProblem(describeProblem(error, "Google sign-in isn't available right now"));
      },
    );
    return () => {
      controller.abort();
      window.google?.accounts.id.cancel();
    };
  }, [clientId, link, parent]);

  return { container: setParent, problem, busy };
}
