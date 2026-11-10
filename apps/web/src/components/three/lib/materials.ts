import * as THREE from "three";

/**
 * Physically based materials shared by every scene, in the glass palette: sunflower for money.
 * Contrast comes from the studio environment's dark flags and bright softboxes, colour shifts
 * from its cool and warm gels.
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
