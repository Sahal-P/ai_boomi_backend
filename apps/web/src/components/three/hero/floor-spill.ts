import * as THREE from "three";

/** Emitters the floor shader evaluates; unused slots get zero radiance. */
export const SPILL_EMITTERS = 3;

export type SpillUniforms = {
  uSpillCorners: { value: THREE.Vector3[] };
  uSpillRadiance: { value: THREE.Color[] };
};

/**
 * Corners (in winding order) of a slab's LED-lit underside: a downward-facing rectangle of
 * the slab's footprint, just below its bottom face, turned by the slab's yaw.
 */
export function slabEmitterCorners(
  centre: readonly [number, number, number],
  width: number,
  depth: number,
  yaw: number,
): THREE.Vector3[] {
  const axis = new THREE.Vector3(0, 1, 0);
  return [
    [-width / 2, -depth / 2],
    [width / 2, -depth / 2],
    [width / 2, depth / 2],
    [-width / 2, depth / 2],
  ].map(([x = 0, z = 0]) =>
    new THREE.Vector3(x, 0, z).applyAxisAngle(axis, yaw).add(new THREE.Vector3(centre[0], centre[1], centre[2])),
  );
}

export function createSpillUniforms(): SpillUniforms {
  return {
    uSpillCorners: { value: Array.from({ length: SPILL_EMITTERS * 4 }, () => new THREE.Vector3(0, -1, 0)) },
    uSpillRadiance: { value: Array.from({ length: SPILL_EMITTERS }, () => new THREE.Color(0, 0, 0)) },
  };
}

const SPILL_GLSL = /* glsl */ `
#define SPILL_EMITTERS ${SPILL_EMITTERS}
uniform vec3 uSpillCorners[SPILL_EMITTERS * 4];
uniform vec3 uSpillRadiance[SPILL_EMITTERS];
varying vec3 vSpillWorld;

// One edge term of Lambert's polygon form factor for an upward-facing receiver (normal +Y).
float spillEdge(vec3 a, vec3 b) {
  vec3 c = cross(a, b);
  return acos(clamp(dot(a, b), -0.9999, 0.9999)) * c.y / max(length(c), 1e-5);
}

// Diffuse radiance from uniform rectangular emitters: albedo is applied by the caller.
vec3 floorSpill(vec3 p) {
  vec3 total = vec3(0.0);
  for (int i = 0; i < SPILL_EMITTERS; i++) {
    vec3 a = normalize(uSpillCorners[i * 4] - p);
    vec3 b = normalize(uSpillCorners[i * 4 + 1] - p);
    vec3 c = normalize(uSpillCorners[i * 4 + 2] - p);
    vec3 d = normalize(uSpillCorners[i * 4 + 3] - p);
    float formFactor = abs(spillEdge(a, b) + spillEdge(b, c) + spillEdge(c, d) + spillEdge(d, a)) * 0.5 / PI;
    total += uSpillRadiance[i] * formFactor;
  }
  return total;
}
`;

/**
 * Lights a floor material with the slabs' LED underglow using the exact diffuse
 * irradiance of uniform rectangular emitters (Lambert's polygon form factor): the same
 * spill an area light gives a matte floor, without three's 110 KB LTC tables and without
 * evaluating area lights on every other surface in the scene.
 */
export function applyFloorSpill(material: THREE.MeshStandardMaterial, uniforms: SpillUniforms): void {
  material.onBeforeCompile = (shader) => {
    Object.assign(shader.uniforms, uniforms);
    shader.vertexShader = shader.vertexShader
      .replace("#include <common>", "#include <common>\nvarying vec3 vSpillWorld;")
      .replace("#include <begin_vertex>", "#include <begin_vertex>\nvSpillWorld = (modelMatrix * vec4(transformed, 1.0)).xyz;");
    shader.fragmentShader = shader.fragmentShader
      .replace("#include <common>", `#include <common>\n${SPILL_GLSL}`)
      .replace(
        "#include <lights_fragment_end>",
        "#include <lights_fragment_end>\nreflectedLight.directDiffuse += diffuseColor.rgb * floorSpill(vSpillWorld);",
      );
  };
  material.customProgramCacheKey = () => "floor-spill";
}
