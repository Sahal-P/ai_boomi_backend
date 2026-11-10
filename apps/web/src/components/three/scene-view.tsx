"use client";

import { PerspectiveCamera, View } from "@react-three/drei";
import { Suspense, type ReactNode } from "react";

import type { SceneSpec } from "./scene-spec";
import { RibbonScene } from "./scenes/ribbon";
import { ProductStudioEnvironment } from "./studio-environment";

type Vec3 = [number, number, number];

/** Camera and studio per scene: metals want the dark cove, pastels and glass the light one. */
const STAGES: Record<SceneSpec["name"], { position: Vec3; fov: number; tone: "dark" | "light" }> = {
  ribbon: { position: [0, 0.2, 7.4], fov: 34, tone: "light" },
};

function renderScene(spec: SceneSpec): ReactNode {
  switch (spec.name) {
    case "ribbon":
      return <RibbonScene />;
  }
}

/**
 * Renders one scene into the shared SceneLayer canvas, tracking `className`'s box. Lit by
 * the product studio (softboxes + dark cove) and one crisp key for specular sparkle;
 * each scene owns its choreography.
 */
type SceneViewProps = {
  spec: SceneSpec;
  className: string;
};

export default function SceneView({ spec, className }: SceneViewProps) {
  const stage = STAGES[spec.name];
  return (
    <View className={className}>
      <PerspectiveCamera makeDefault position={stage.position} fov={stage.fov} onUpdate={(self) => self.lookAt(0, 0, 0)} />
      <ProductStudioEnvironment tone={stage.tone} />
      <directionalLight position={[-3, 5, 4]} intensity={1.2} color="#fff6ec" />
      <Suspense fallback={null}>{renderScene(spec)}</Suspense>
    </View>
  );
}
