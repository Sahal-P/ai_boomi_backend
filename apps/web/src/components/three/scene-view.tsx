"use client";

import { PerspectiveCamera, View } from "@react-three/drei";
import { Suspense, type ReactNode } from "react";

import type { SceneSpec } from "./scene-spec";
import { CheckOrbScene } from "./scenes/check-orb";
import { CoinStackScene } from "./scenes/coin-stack";
import { CoinSwirlScene } from "./scenes/coin-swirl";
import { InboxSlabScene } from "./scenes/inbox-slab";
import { PrivacyVaultScene } from "./scenes/privacy-vault";
import { RibbonScene } from "./scenes/ribbon";
import { VoiceOrbScene } from "./scenes/voice-orb";
import { ProductStudioEnvironment } from "./studio-environment";

type Vec3 = [number, number, number];

/** Camera and studio per scene: metals want the dark cove, pastels and glass the light one. */
const STAGES: Record<SceneSpec["name"], { position: Vec3; fov: number; tone: "dark" | "light" }> = {
  "coin-swirl": { position: [0, 0, 7], fov: 30, tone: "dark" },
  "check-orb": { position: [0, 0, 5.8], fov: 30, tone: "dark" },
  "voice-orb": { position: [0, 0, 4.6], fov: 32, tone: "light" },
  "coin-stack": { position: [0, 1.9, 7.6], fov: 30, tone: "dark" },
  "privacy-vault": { position: [0, 0.9, 5.6], fov: 30, tone: "light" },
  ribbon: { position: [0, 0.2, 7.4], fov: 34, tone: "light" },
  "inbox-slab": { position: [0, 1.2, 5.4], fov: 30, tone: "light" },
};

function renderScene(spec: SceneSpec, revealed: boolean): ReactNode {
  switch (spec.name) {
    case "coin-swirl":
      return <CoinSwirlScene merge={spec.merge ?? 0} loop={spec.loop ?? false} />;
    case "check-orb":
      return <CheckOrbScene />;
    case "voice-orb":
      return <VoiceOrbScene state={spec.state ?? "idle"} level={spec.level} />;
    case "coin-stack":
      return <CoinStackScene values={spec.values} revealed={revealed} />;
    case "privacy-vault":
      return <PrivacyVaultScene />;
    case "ribbon":
      return <RibbonScene />;
    case "inbox-slab":
      return <InboxSlabScene />;
  }
}

/**
 * Renders one scene into the shared SceneLayer canvas, tracking `className`'s box. Lit by
 * the product studio (softboxes + dark cove) and one crisp key for specular sparkle;
 * each scene owns its choreography.
 */
type SceneViewProps = {
  spec: SceneSpec;
  /** True once the slot is substantially on screen; starts reveal choreography. */
  revealed: boolean;
  className: string;
};

export default function SceneView({ spec, revealed, className }: SceneViewProps) {
  const stage = STAGES[spec.name];
  return (
    <View className={className}>
      <PerspectiveCamera makeDefault position={stage.position} fov={stage.fov} onUpdate={(self) => self.lookAt(0, 0, 0)} />
      <ProductStudioEnvironment tone={stage.tone} />
      <directionalLight position={[-3, 5, 4]} intensity={1.2} color="#fff6ec" />
      <Suspense fallback={null}>{renderScene(spec, revealed)}</Suspense>
    </View>
  );
}
