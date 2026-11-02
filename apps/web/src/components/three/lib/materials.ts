import * as THREE from "three";

/**
 * Physically based materials shared by every scene, in the glass palette: sunflower for money
 * and clear glass. Contrast comes from the studio environment's dark flags and bright
 * softboxes, colour shifts from its cool and warm gels.
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

type GlassOptions = {
  roughness?: number;
  thickness?: number;
  dispersion?: number;
  tint?: THREE.ColorRepresentation;
  absorption?: number;
};

/**
 * Clear optical glass with real refraction; `dispersion` splits bright edges into faint
 * spectral fringes. Needs something opaque behind it: three clears its transmission buffer to
 * 50% white on the transparent shared canvas, so glass over nothing refracts a white haze.
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
