"use client";

import { useState } from "react";
import Link from "next/link";
import { useHouseholdLogin } from "@/hooks/use-household";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function HouseholdLogin() {
  const [password, setPassword] = useState("");
  const login = useHouseholdLogin();
  return <main className="grid min-h-screen place-items-center bg-aurora p-6">
    <section className="surface w-full max-w-md rounded-3xl p-8" aria-labelledby="login-title">
      <Link href="/" className="text-sm font-semibold text-violet">FinBoy</Link>
      <h1 id="login-title" className="mt-6 text-3xl font-semibold tracking-tight">Your private money space.</h1>
      <p className="mt-3 text-ink-soft">Sign in with your household password to access your records.</p>
      <form className="mt-8 space-y-4" onSubmit={(event) => { event.preventDefault(); const submitted = password; setPassword(""); void login.submit(submitted); }}>
        <label className="block space-y-2"><span className="text-sm font-medium">Household password</span>
          <Input type="password" name="password" autoComplete="current-password" required maxLength={256} value={password} onChange={(event) => setPassword(event.target.value)} />
        </label>
        {login.error && <p role="alert" className="text-sm text-destructive">{login.error}</p>}
        <Button type="submit" className="w-full" disabled={login.busy}>{login.busy ? "Signing in…" : "Sign in"}</Button>
      </form>
      <p className="mt-6 text-xs text-ink-soft">Private household access. There is no public sign-up.</p>
    </section>
  </main>;
}
