import { ArrowRight, Sparkles } from "lucide-react";
import { notFound } from "next/navigation";

import { AnimatedAmount } from "@/components/motion/animated-amount";
import { SceneLayerMount, SceneSlot } from "@/components/three/scene-slot";
import type { SceneSpec } from "@/components/three/scene-spec";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

const scenes: Array<{ title: string; usage: string; spec: SceneSpec }> = [
  { title: "Coin swirl", usage: "Duplicates merged · landing features", spec: { name: "coin-swirl" } },
  { title: "Coin swirl · loop", usage: "Import done / merge action", spec: { name: "coin-swirl", loop: true } },
  { title: "Check orb", usage: "Verified / confirm actions", spec: { name: "check-orb" } },
  { title: "Voice orb", usage: "Assistant (idle)", spec: { name: "voice-orb" } },
  { title: "Voice orb · thinking", usage: "Assistant while answering", spec: { name: "voice-orb", state: "thinking" } },
  { title: "Coin stack", usage: "SIP simulator", spec: { name: "coin-stack", values: [1, 0.6, 0.16, 0.08, 0.16] } },
  { title: "Privacy vault", usage: "Privacy & trust", spec: { name: "privacy-vault" } },
  { title: "Inbox slab", usage: "Connect Gmail / import", spec: { name: "inbox-slab" } },
  { title: "Ribbon", usage: "Closing call to action", spec: { name: "ribbon" } },
];

const swatches = [
  ["Ink", "bg-ink"],
  ["Canvas", "bg-canvas"],
  ["Lilac", "bg-lilac"],
  ["Violet", "bg-violet"],
  ["Orchid", "bg-orchid"],
  ["Magenta", "bg-magenta"],
  ["Gold", "bg-gold"],
  ["Sky", "bg-sky"],
  ["Positive", "bg-positive"],
  ["Negative", "bg-negative"],
] as const;

export const metadata = { title: "FinBoy design system" };

/** Internal catalogue of tokens, UI primitives and the 3D scene kit (not served in production). */
export default function StyleguidePage() {
  if (process.env.NODE_ENV === "production") notFound();
  return (
    <main className="bg-aurora min-h-screen px-6 py-16 sm:px-10 lg:px-16">
      <SceneLayerMount />
      <div className="mx-auto max-w-[1360px] space-y-20">
        <header>
          <p className="eyebrow text-violet">Design system</p>
          <h1 className="mt-3 text-5xl font-semibold tracking-[-0.04em] text-ink">FinBoy · Light 3D</h1>
          <p className="mt-4 max-w-2xl text-ink-soft">
            Tokens live in <code className="rounded bg-white px-1.5 py-0.5 text-sm">globals.css</code>; primitives in{" "}
            <code className="rounded bg-white px-1.5 py-0.5 text-sm">components/ui</code>; 3D in{" "}
            <code className="rounded bg-white px-1.5 py-0.5 text-sm">{"<SceneSlot spec={...} />"}</code>. See
            docs/design-system.md.
          </p>
        </header>

        <section aria-labelledby="tokens" className="space-y-6">
          <h2 id="tokens" className="text-2xl font-semibold tracking-[-0.02em] text-ink">Colour</h2>
          <ul className="grid grid-cols-2 gap-4 sm:grid-cols-5">
            {swatches.map(([name, swatch]) => (
              <li key={name} className="surface rounded-2xl p-3">
                <span className={`block h-14 rounded-xl ring-1 ring-ink/5 ${swatch}`} />
                <span className="mt-2 block text-sm font-semibold text-ink">{name}</span>
              </li>
            ))}
          </ul>
        </section>

        <section aria-labelledby="primitives" className="space-y-6">
          <h2 id="primitives" className="text-2xl font-semibold tracking-[-0.02em] text-ink">Primitives</h2>
          <div className="flex flex-wrap items-center gap-3">
            <Button>
              Connect Gmail <ArrowRight data-icon="inline-end" />
            </Button>
            <Button variant="brand">
              <Sparkles data-icon="inline-start" /> Ask FinBoy
            </Button>
            <Button variant="glass">Try the demo mailbox</Button>
            <Button variant="outline">Edit</Button>
            <Button variant="secondary">Keep separate</Button>
            <Button variant="ghost">Not mine</Button>
            <Button variant="destructive">Disconnect</Button>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Badge>Food &amp; dining</Badge>
            <Badge variant="solid">3 sources</Badge>
            <Badge variant="positive">Confirmed</Badge>
            <Badge variant="warning">Needs review</Badge>
            <Badge variant="outline">Read-only</Badge>
          </div>
          <div className="grid gap-6 md:grid-cols-3">
            <Card>
              <CardHeader>
                <CardDescription>Estimated unallocated</CardDescription>
                <CardTitle className="text-4xl">
                  <AnimatedAmount amountMinor={1_478_000} />
                </CardTitle>
              </CardHeader>
              <CardContent className="text-xs text-ink-subtle">
                Based on email-derived and confirmed records. Your actual bank balance may differ.
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardDescription>Tracked outflows · October</CardDescription>
                <CardTitle className="text-4xl">
                  <AnimatedAmount amountMinor={3_742_000} />
                </CardTitle>
              </CardHeader>
              <CardContent>
                <Badge variant="warning">2 awaiting confirmation</Badge>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle>Correct category</CardTitle>
                <CardDescription>HOTEL ARYA · ₹1,250</CardDescription>
              </CardHeader>
              <CardContent className="flex gap-2">
                <Input aria-label="Category" defaultValue="Food & dining" />
                <Button size="default">Save</Button>
              </CardContent>
            </Card>
          </div>
        </section>

        <section aria-labelledby="scenes" className="space-y-6">
          <h2 id="scenes" className="text-2xl font-semibold tracking-[-0.02em] text-ink">3D scene kit</h2>
          <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {scenes.map((scene) => (
              <article key={scene.title} className="surface overflow-hidden rounded-3xl">
                <SceneSlot spec={scene.spec} className="h-72 bg-[radial-gradient(circle_at_50%_40%,#ffffff,#f1eefb)]" />
                <div className="border-t px-6 py-4">
                  <h3 className="font-semibold text-ink">{scene.title}</h3>
                  <p className="text-sm text-ink-soft">{scene.usage}</p>
                </div>
              </article>
            ))}
          </div>
        </section>
      </div>
    </main>
  );
}
