import { useFrame } from "@react-three/fiber";
import type { RefObject } from "react";
import * as THREE from "three";

type MaterialSource = THREE.Material | RefObject<THREE.Mesh | null> | null | undefined;

function materialsOf(source: MaterialSource): THREE.Material[] {
  if (!source) return [];
  if (source instanceof THREE.Material) return [source];
  const material = source.current?.material;
  if (!material) return [];
  return Array.isArray(material) ? material : [material];
}

/**
 * three r186 ignores `envMapIntensity` for materials that inherit `scene.environment`;
 * the scene-wide `environmentIntensity` wins. Glass and metals get the environment as
 * their own `envMap` so they keep bright reflections while matte surfaces stay dim.
 * Pass materials directly, or a mesh ref to use whatever material that mesh renders with.
 */
export function useOwnReflections(sources: readonly MaterialSource[]): void {
  useFrame(({ scene }) => {
    const environment = scene.environment;
    if (!environment) return;
    for (const source of sources) {
      for (const material of materialsOf(source)) {
        if (material instanceof THREE.MeshStandardMaterial && material.envMap !== environment) {
          material.envMap = environment;
          material.needsUpdate = true;
        }
      }
    }
  });
}
