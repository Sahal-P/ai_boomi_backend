"use client";

import { useLoader } from "@react-three/fiber";
import * as THREE from "three";
import { MeshoptDecoder } from "three/examples/jsm/libs/meshopt_decoder.module.js";
import { GLTFLoader, type GLTF } from "three/examples/jsm/loaders/GLTFLoader.js";

/** Sculpted in Blender by scripts/3d/build_assets.py; rebuild with `pnpm assets:3d`. */
const MODELS = {
  coin: "/models/coin.glb",
  dome: "/models/check-dome.glb",
} as const;

// three's own loader + decoder (both r186) — drei's bundled decoder predates gltfpack 1.x.
function withMeshopt(loader: GLTFLoader): void {
  loader.setMeshoptDecoder(MeshoptDecoder);
}

function geometryOf(gltf: GLTF, name: string): THREE.BufferGeometry {
  const object = gltf.scene.getObjectByName(name);
  if (!(object instanceof THREE.Mesh)) throw new Error(`Model mesh "${name}" is missing`);
  return object.geometry;
}

/** "full": 84-ridge reeded edge for close-ups; "lite": 48 broad ridges for small or many coins. */
export type CoinDetail = "full" | "lite";

/**
 * Minted ₹ coin, radius 1 and 0.2 thick, obverse facing +Z. Geometry is cached and shared
 * by every caller — never dispose it.
 */
export function useCoinGeometry(detail: CoinDetail): THREE.BufferGeometry {
  return geometryOf(useLoader(GLTFLoader, MODELS.coin, withMeshopt), detail === "full" ? "Coin" : "CoinLite");
}

/** Verification dome, radius 1, check face toward +Z. Cached and shared — never dispose it. */
export function useDomeGeometry(): THREE.BufferGeometry {
  return geometryOf(useLoader(GLTFLoader, MODELS.dome, withMeshopt), "CheckDome");
}

/** Starts both downloads as soon as the 3D bundle loads. */
export function preloadModels(): void {
  useLoader.preload(GLTFLoader, MODELS.coin, withMeshopt);
  useLoader.preload(GLTFLoader, MODELS.dome, withMeshopt);
}
