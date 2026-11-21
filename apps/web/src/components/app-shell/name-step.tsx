"use client";

import { useId, useState } from "react";
import { Brand } from "@/components/brand";
import { ProblemNotice } from "@/components/feedback/problem-notice";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { saveName } from "@/lib/api/auth";
import { describeProblem, type Problem } from "@/lib/messages";

/** Asked once before the app opens (docs/names-search-round/contract.md): the name only. */
export function NameStep({ onSaved }: { onSaved: () => Promise<void> }) {
  const ids = useId();
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<Problem | null>(null);
  return (
    <main className="bg-field bg-wallpaper grid min-h-dvh place-items-center px-4 py-10 sm:px-6">
      <div className="w-full max-w-md">
        <Brand />
        <section aria-labelledby={`${ids}-title`} className="surface mt-6 rounded-3xl p-6 sm:p-8">
          <h1 id={`${ids}-title`} className="text-[1.75rem] leading-tight font-medium tracking-[-0.025em]">
            What should we call you?
          </h1>
          <form
            className="mt-6 space-y-4"
            onSubmit={async (event) => {
              event.preventDefault();
              setBusy(true);
              setProblem(null);
              try {
                await saveName(name.trim());
                await onSaved();
              } catch (error) {
                setProblem(describeProblem(error, "Your name wasn't saved"));
              } finally {
                setBusy(false);
              }
            }}
          >
            <div>
              <label htmlFor={`${ids}-name`} className="text-sm font-semibold">
                Your name
              </label>
              <Input
                id={`${ids}-name`}
                autoComplete="name"
                required
                maxLength={60}
                value={name}
                aria-invalid={problem ? true : undefined}
                aria-describedby={problem ? `${ids}-problem` : undefined}
                onChange={(event) => setName(event.target.value)}
                className="mt-1.5"
              />
            </div>
            {problem && <ProblemNotice id={`${ids}-problem`} problem={problem} />}
            <Button type="submit" size="lg" className="w-full" disabled={busy || !name.trim()}>
              {busy ? "Saving…" : "Continue"}
            </Button>
          </form>
        </section>
      </div>
    </main>
  );
}
