import * as THREE from "three";

import type { QualityTier } from "./quality";

/**
 * Physically based materials shared by every scene. Metals carry no clearcoat (a lacquer
 * layer washes their colour into plastic); colour comes from the base and thin-film
 * iridescence, contrast from the studio environment's dark flags and bright softboxes.
 */

/** Minted gold: warm, saturated F0 with a polished but not mirror finish. */
export function createGold(roughness = 0.19): THREE.MeshPhysicalMaterial {
  return new THREE.MeshPhysicalMaterial({ color: "#f3b84e", metalness: 1, roughness });
}

/**
 * Anodised aluminium with a thin-film sheen: pink → peach → violet as faces turn. A narrow
 * film-thickness range keeps the shift within warm tones instead of swinging to blue.
 */
export function createAnodised(color: THREE.ColorRepresentation, roughness = 0.24): THREE.MeshPhysicalMaterial {
  return new THREE.MeshPhysicalMaterial({
    color,
    metalness: 1,
    roughness,
    iridescence: 0.6,
    iridescenceIOR: 1.5,
    iridescenceThicknessRange: [320, 520],
  });
}

/** Polished chrome with a strong interference film (violet face, cyan-blue grazing rims). */
export function createIridescentChrome(color: THREE.ColorRepresentation, roughness = 0.09): THREE.MeshPhysicalMaterial {
  return new THREE.MeshPhysicalMaterial({
    color,
    metalness: 1,
    roughness,
    iridescence: 1,
    iridescenceIOR: 1.33,
    iridescenceThicknessRange: [140, 620],
  });
}

/** Opaque satin acrylic: milky body, soft sheen, lacquered highlights. No transmission pass. */
export function createSatinAcrylic(): THREE.MeshPhysicalMaterial {
  return new THREE.MeshPhysicalMaterial({
    color: "#efe9fb",
    roughness: 0.32,
    sheen: 1,
    sheenColor: new THREE.Color("#ffffff"),
    sheenRoughness: 0.55,
    clearcoat: 0.5,
    clearcoatRoughness: 0.28,
  });
}

/**
 * Satin-frosted acrylic for opaque canvases (the hero). Low tier gets the satin stand-in.
 * Don't use transmission in the shared transparent canvas: see `createSurfaceGlass`.
 */
export function createFrostedAcrylic(tier: QualityTier): THREE.MeshPhysicalMaterial {
  if (tier === "low") return createSatinAcrylic();
  // Partial transmission: the lit, milky body of real frosted acrylic plus a blurred view
  // through it. Full transmission reads as clear glass and vanishes on a white set.
  return new THREE.MeshPhysicalMaterial({
    color: "#ffffff",
    roughness: 0.26,
    transmission: 0.72,
    thickness: 0.4,
    ior: 1.49,
    attenuationColor: new THREE.Color("#e2d6ff"),
    attenuationDistance: 1.1,
    sheen: 0.25,
    sheenColor: new THREE.Color("#ffffff"),
    sheenRoughness: 0.4,
    // A polished skin over the frosted body: crisp highlights run along the lips.
    clearcoat: 1,
    clearcoatRoughness: 0.08,
  });
}

type GlassOptions = {
  roughness?: number;
  thickness?: number;
  dispersion?: number;
  tint?: THREE.ColorRepresentation;
  absorption?: number;
};

/**
 * Glass for the shared transparent canvas. three clears its transmission buffer to 50%
 * white whenever the canvas is transparent, so transmissive glass there refracts a white
 * haze (a glowing box). This is alpha-blended instead: the page shows through at true
 * opacity and Fresnel reflections carry the form; double-sided so inner faces reflect too
 * (three draws the back faces first).
 */
export function createSurfaceGlass(tint: THREE.ColorRepresentation = "#f6f2ff", opacity = 0.2): THREE.MeshPhysicalMaterial {
  return new THREE.MeshPhysicalMaterial({
    color: tint,
    roughness: 0.05,
    transparent: true,
    opacity,
    side: THREE.DoubleSide,
    depthWrite: false,
    ior: 1.5,
    specularIntensity: 1,
    clearcoat: 1,
    clearcoatRoughness: 0.04,
  });
}

/**
 * Clear optical glass with real refraction; `dispersion` splits bright edges into faint
 * spectral fringes. Needs something opaque behind it (see `createSurfaceGlass`).
 */
export function createGlass({
  roughness = 0.03,
  thickness = 0.8,
  dispersion = 0.2,
  tint = "#efe9ff",
  absorption = 3,
}: GlassOptions = {}): THREE.MeshPhysicalMaterial {
  return new THREE.MeshPhysicalMaterial({
    color: "#ffffff",
    roughness,
    transmission: 1,
    thickness,
    ior: 1.5,
    dispersion,
    attenuationColor: new THREE.Color(tint),
    attenuationDistance: absorption,
    specularIntensity: 1,
  });
}

/** Light-emitting strip. HDR so it blooms in composited scenes; `toneMapped` off elsewhere. */
export function createNeon(color: THREE.ColorRepresentation, strength = 6): THREE.MeshBasicMaterial {
  const material = new THREE.MeshBasicMaterial({ color: new THREE.Color(color).multiplyScalar(strength) });
  material.toneMapped = false;
  return material;
}
