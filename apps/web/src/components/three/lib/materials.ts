import * as THREE from "three";

/**
 * Physically based materials shared by every scene, in the glass palette: sunflower for money,
 * ink for decisions, pearl and clear glass for the rest. Contrast comes from the studio
 * environment's dark flags and bright softboxes, colour shifts from its cool and warm gels.
 */

/**
 * Sunflower for money objects. Half metal under a clear lacquer: a full metal mirrors the dark
 * cove and reads as brass, while the yellow body keeps every face the theme's money colour.
 */
export function createSunflower(roughness = 0.19, color: THREE.ColorRepresentation = "#fed234"): THREE.MeshPhysicalMaterial {
  return new THREE.MeshPhysicalMaterial({
    color,
    metalness: 0.5,
    roughness: roughness + 0.06,
    clearcoat: 0.6,
    clearcoatRoughness: 0.12,
  });
}

/** Lacquered ink, the black pills in 3D: a dark body with crisp highlights and bright rims. */
export function createInk(roughness = 0.3): THREE.MeshPhysicalMaterial {
  return new THREE.MeshPhysicalMaterial({
    color: "#14171c",
    roughness,
    clearcoat: 1,
    clearcoatRoughness: 0.06,
  });
}

/** Opaque satin acrylic: pearl body, soft sheen, lacquered highlights. No transmission pass. */
export function createSatinAcrylic(): THREE.MeshPhysicalMaterial {
  return new THREE.MeshPhysicalMaterial({
    color: "#eef1f4",
    roughness: 0.32,
    sheen: 1,
    sheenColor: new THREE.Color("#ffffff"),
    sheenRoughness: 0.55,
    clearcoat: 0.5,
    clearcoatRoughness: 0.28,
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
export function createSurfaceGlass(tint: THREE.ColorRepresentation = "#f4f7f9", opacity = 0.2): THREE.MeshPhysicalMaterial {
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
  tint = "#eef4f7",
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
