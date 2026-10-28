"use client";

import { KeyRound, LoaderCircle, MessageCircle, QrCode, RotateCcw } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import QRCode from "qrcode";
import { useEffect, useId, useState } from "react";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { ThinkingOrb } from "@/components/feedback/thinking-orb";
import { Button, buttonVariants } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useGoogleSignIn } from "@/hooks/use-google-sign-in";
import { useSignIn } from "@/hooks/use-household";
import { useWhatsAppSignIn, type WhatsAppPhase } from "@/hooks/use-whatsapp-sign-in";
import { chatLink, getSession, type SessionView } from "@/lib/api/auth";
import { isAbort } from "@/lib/api/http";
import { describeProblem, type Problem } from "@/lib/messages";
import { cn } from "@/lib/utils";

type Options = SessionView["sign_in"];

function useSignInOptions() {
  const [options, setOptions] = useState<Options | null>(null);
  const [problem, setProblem] = useState<Problem | null>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    getSession(controller.signal).then(
      (session) => {
        if (!controller.signal.aborted) setOptions(session.sign_in);
      },
      (error: unknown) => {
        if (controller.signal.aborted || isAbort(error)) return;
        setProblem(describeProblem(error, "Sign-in options couldn't load"));
      },
    );
    return () => controller.abort();
  }, [attempt]);
  return {
    options,
    problem,
    retry: () => {
      setProblem(null);
      setAttempt((value) => value + 1);
    },
  };
}

/** Shown size in CSS pixels: big enough for a phone camera held at arm's length. */
const QR_SIZE = 256;

/** The scannable twin of the WhatsApp link, for people signing in on a computer. */
function LinkCode({ link }: { link: string }) {
  const [image, setImage] = useState<string | null>(null);
  useEffect(() => {
    let current = true;
    // Drawn at twice the shown size so the modules stay sharp on high-density screens.
    QRCode.toDataURL(link, { margin: 1, width: QR_SIZE * 2, errorCorrectionLevel: "M" }).then(
      (url) => {
        if (current) setImage(url);
      },
      () => undefined,
    );
    return () => {
      current = false;
    };
  }, [link]);
  if (!image) return <div className="size-64 rounded-2xl bg-white/60" aria-hidden="true" />;
  // Drawn locally as a data URL: nothing to optimise and nothing fetched.
  return (
    <Image
      src={image}
      unoptimized
      width={QR_SIZE}
      height={QR_SIZE}
      alt="QR code that opens FinBoy's WhatsApp chat"
      className="rounded-2xl bg-white p-3"
    />
  );
}

function WhatsAppSignIn({ phase, onOpened, onRestart, purpose }: {
  phase: WhatsAppPhase;
  onOpened: () => void;
  onRestart: () => void;
  purpose: "sign_in" | "link";
}) {
  const label = purpose === "link" ? "Link my WhatsApp" : "Continue with WhatsApp";
  const big = cn(buttonVariants({ size: "lg" }), "h-14 w-full gap-3 text-base");
  if (phase.step === "off") return null;
  if (phase.step === "problem") {
    return <ProblemNotice problem={phase.problem} onRetry={onRestart} />;
  }
  if (phase.step === "declined") {
    return (
      <div role="status" className="rounded-2xl bg-white/70 p-4 text-sm leading-relaxed">
        <p className="font-semibold">
          {phase.full ? "FinBoy is full for now" : "You tapped No on WhatsApp"}
        </p>
        <p className="mt-1 text-ink-soft">
          {phase.full
            ? "New accounts will open again soon. Send JOIN to FinBoy on WhatsApp to keep your place in line."
            : "Nobody was signed in and nothing was kept."}
        </p>
        <Button type="button" variant="outline" className="mt-3" onClick={onRestart}>
          <RotateCcw aria-hidden="true" /> Start again
        </Button>
      </div>
    );
  }
  if (phase.step !== "ready") {
    return (
      <span className={cn(big, "pointer-events-none opacity-80")} role="status">
        <LoaderCircle className="size-5 motion-safe:animate-spin" aria-hidden="true" />
        {phase.step === "finishing" ? "Signing you in…" : "Getting WhatsApp ready…"}
      </span>
    );
  }
  const { start, opened } = phase;
  return (
    <div className="space-y-3">
      {start.link ? (
        <a href={start.link} target="_blank" rel="noopener noreferrer" className={big} onClick={onOpened}>
          <MessageCircle className="size-5" aria-hidden="true" /> {label}
        </a>
      ) : null}
      {opened ? (
        <p role="status" className="flex items-center gap-3 rounded-2xl bg-white/70 p-3 text-sm leading-relaxed">
          <ThinkingOrb state="connecting" size={20} />
          <span>
            Waiting for you on WhatsApp. Tap <strong>Send</strong>, then tap <strong>✅ Yes</strong> — this
            page continues by itself.
          </span>
        </p>
      ) : (
        <p className="text-sm leading-relaxed text-sunflower-ink">
          WhatsApp opens with a message ready. Tap <strong>Send</strong>, then <strong>✅ Yes</strong>.
          No password, nothing to remember.
        </p>
      )}
      {start.link ? (
        <details className="hidden rounded-2xl bg-white/55 p-3 text-sm sm:block" open={!opened}>
          <summary className="flex cursor-pointer items-center gap-2 font-semibold">
            <QrCode className="size-4" aria-hidden="true" /> On a computer? Scan with your phone
          </summary>
          <div className="mt-4 flex flex-col items-center gap-3 pb-1 text-center">
            <LinkCode link={start.link} />
            <p className="max-w-[18rem] leading-relaxed text-ink-soft">
              Point your phone&apos;s camera here. WhatsApp opens with your code{" "}
              <span className="font-mono font-semibold text-ink">{start.code}</span> typed in.
            </p>
          </div>
        </details>
      ) : null}
      {opened ? (
        <button type="button" className="text-xs font-semibold underline underline-offset-4" onClick={onRestart}>
          Didn&apos;t work? Get a new code
        </button>
      ) : null}
    </div>
  );
}

function PasswordSignIn({ onSignedIn, only }: { onSignedIn: () => void; only: boolean }) {
  const [password, setPassword] = useState("");
  const errorId = useId();
  const inputId = useId();
  const login = useSignIn(onSignedIn);
  return (
    <details className="rounded-2xl bg-white/45 p-3 text-sm" open={only || undefined}>
      <summary className="flex cursor-pointer items-center gap-2 font-semibold">
        <KeyRound className="size-4" aria-hidden="true" /> Household password
      </summary>
      <form
        className="mt-3 space-y-3"
        onSubmit={(event) => {
          event.preventDefault();
          const submitted = password;
          setPassword("");
          void login.submit(submitted);
        }}
      >
        <label htmlFor={inputId} className="sr-only">
          Household password
        </label>
        <Input
          id={inputId}
          type="password"
          autoComplete="current-password"
          required
          maxLength={256}
          value={password}
          aria-invalid={login.problem?.code === "invalid_credentials" || undefined}
          aria-describedby={login.problem ? errorId : undefined}
          onChange={(event) => setPassword(event.target.value)}
          className="h-11 rounded-2xl border-2 border-ink bg-white"
        />
        {login.problem && <ProblemNotice id={errorId} problem={login.problem} />}
        <Button type="submit" disabled={login.busy}>
          {login.busy ? "Signing in…" : "Sign in"}
        </Button>
      </form>
    </details>
  );
}

/**
 * Every way into FinBoy, in order of ease: WhatsApp (one tap, then ✅ on the phone), Google, and
 * the owner's household password. Used on the sign-in page and in place when a session ends.
 */
export function SignInOptions({ onSignedIn }: { onSignedIn: () => void }) {
  const { options, problem, retry } = useSignInOptions();
  const whatsapp = useWhatsAppSignIn({ enabled: options?.whatsapp ?? false, onDone: onSignedIn });
  const { container: googleButton, problem: googleProblem, busy: googleBusy } = useGoogleSignIn({
    clientId: options?.google_client_id ?? null,
    onDone: onSignedIn,
  });
  if (problem) return <ProblemNotice problem={problem} onRetry={retry} />;
  if (!options) {
    return (
      <p role="status" className="flex items-center gap-3 text-sm">
        <LoaderCircle className="size-4 motion-safe:animate-spin" aria-hidden="true" /> Loading sign-in…
      </p>
    );
  }
  const anyWay = options.whatsapp || options.google_client_id || options.password;
  return (
    <div className="space-y-4">
      {!options.signup_open && (options.whatsapp || options.google_client_id) ? (
        <p className="rounded-2xl bg-white/70 p-3 text-xs leading-relaxed">
          New accounts are full for now. Already have one? Sign in as usual.
        </p>
      ) : null}
      <WhatsAppSignIn
        phase={whatsapp.phase}
        onOpened={whatsapp.opened}
        onRestart={whatsapp.restart}
        purpose="sign_in"
      />
      {options.google_client_id ? (
        <div className="space-y-2">
          {options.whatsapp ? (
            <p className="flex items-center gap-3 text-xs font-semibold text-sunflower-ink" aria-hidden="true">
              <span className="h-px flex-1 bg-ink/15" /> or <span className="h-px flex-1 bg-ink/15" />
            </p>
          ) : null}
          <div ref={googleButton} className="flex min-h-11 justify-center" aria-busy={googleBusy} />
          {googleProblem && <ProblemNotice problem={googleProblem} />}
        </div>
      ) : null}
      {options.password ? (
        <PasswordSignIn onSignedIn={onSignedIn} only={!options.whatsapp && !options.google_client_id} />
      ) : null}
      {!anyWay ? (
        <p className="rounded-2xl bg-white/70 p-3 text-sm">Sign-in isn&apos;t set up on this server yet.</p>
      ) : null}
      {options.whatsapp && options.whatsapp_number && options.signup_open ? (
        <p className="text-xs leading-relaxed text-sunflower-ink">
          Only want to use WhatsApp?{" "}
          <a
            className="font-semibold text-ink underline underline-offset-4"
            href={chatLink(options.whatsapp_number)}
            target="_blank"
            rel="noopener noreferrer"
          >
            Say hi to FinBoy
          </a>{" "}
          and record money by voice right there.
        </p>
      ) : null}
      <p className="text-xs leading-relaxed text-sunflower-ink">
        By continuing you agree to FinBoy&apos;s{" "}
        <Link href="/terms" className="font-semibold text-ink underline underline-offset-4">
          Terms
        </Link>{" "}
        and{" "}
        <Link href="/privacy-policy" className="font-semibold text-ink underline underline-offset-4">
          Privacy Policy
        </Link>
        .
      </p>
    </div>
  );
}

export { WhatsAppSignIn };
