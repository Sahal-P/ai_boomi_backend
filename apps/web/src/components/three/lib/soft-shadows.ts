import * as THREE from "three";

/** Largest tent half-width (texels) a light's `shadow.radius` can ask for. */
const MAX_TENT = 8;
let patched = false;

/**
 * three r186 filters PCF shadows with 5 Vogel-disk taps rotated per pixel by screen-space
 * noise: at a sun's wide radius that noise stays fixed to the screen while shadows move
 * under the camera, and reads as crawling grain. A fixed disk instead leaves the shadow
 * map's rasterised staircase visible as frayed penumbrae.
 *
 * This swaps in a separable tent filter in texel space. `shadow.radius` is the tent's
 * half-width R in texels (an integer, 1–8). Each tap is a hardware PCF lookup placed
 * between two texels so the pair receives its exact tent weights, so R×R taps filter
 * (2R)² texels: penumbrae are smooth ramps (σ ≈ 0.41·R texels), stable under camera and
 * light motion. If three's chunk changes shape the patch is skipped and three's default
 * filter remains. Must run before any shadow-receiving material compiles.
 */
export function patchStableSoftShadows(): void {
  if (patched) return;
  patched = true;
  const chunk = THREE.ShaderChunk.shadowmap_pars_fragment;
  // Anchored on code, not comments: three's published build strips GLSL comments.
  const fn = chunk.indexOf("float getShadow( sampler2DShadow shadowMap");
  const start = chunk.indexOf("vec2 texelSize = vec2( 1.0 ) / shadowMapSize;", fn);
  const endToken = ") * 0.2;";
  const end = chunk.indexOf(endToken, start);
  const body = chunk.slice(start, end);
  if (fn < 0 || start < 0 || end < 0 || !body.includes("vogelDiskSample") || body.includes("getShadow")) {
    if (process.env.NODE_ENV !== "production") console.warn("soft-shadows: three's PCF chunk changed; patch skipped");
    return;
  }
  const tent = /* glsl */ `// Separable texel-space tent (see soft-shadows.ts): exact per-texel weights.
				float tent = floor( clamp( shadowRadius, 1.0, ${MAX_TENT}.0 ) );
				vec2 texel = shadowCoord.xy * shadowMapSize - 0.5;
				vec2 base = floor( texel );
				vec2 fraction = texel - base;
				float sum = 0.0;
				for ( int j = 0; j < ${MAX_TENT}; j ++ ) {
					if ( float( j ) >= tent ) break;
					float ky = float( 2 * j + 1 ) - tent;
					float wy0 = tent - abs( ky - fraction.y );
					float wy1 = tent - abs( ky + 1.0 - fraction.y );
					float v = ( base.y + ky + wy1 / ( wy0 + wy1 ) + 0.5 ) / shadowMapSize.y;
					for ( int i = 0; i < ${MAX_TENT}; i ++ ) {
						if ( float( i ) >= tent ) break;
						float kx = float( 2 * i + 1 ) - tent;
						float wx0 = tent - abs( kx - fraction.x );
						float wx1 = tent - abs( kx + 1.0 - fraction.x );
						float u = ( base.x + kx + wx1 / ( wx0 + wx1 ) + 0.5 ) / shadowMapSize.x;
						sum += ( wx0 + wx1 ) * ( wy0 + wy1 ) * texture( shadowMap, vec3( u, v, shadowCoord.z ) );
					}
				}
				shadow = sum / ( tent * tent * tent * tent );`;
  THREE.ShaderChunk.shadowmap_pars_fragment = `${chunk.slice(0, start)}${tent}${chunk.slice(end + endToken.length)}`;
}

/**
 * Depth material for translucent casters: a texel checkerboard drops half the caster from
 * the shadow map, and the tent filter (any radius ≥ 2) averages it into a uniform
 * half-strength shadow. Frosted acrylic lets much of the sun through; it shouldn't cast a
 * solid shadow.
 */
export function createTranslucentShadowMaterial(): THREE.MeshDepthMaterial {
  const material = new THREE.MeshDepthMaterial();
  material.onBeforeCompile = (shader) => {
    shader.fragmentShader = shader.fragmentShader.replace(
      "void main() {",
      /* glsl */ `void main() {
  if ( mod( floor( gl_FragCoord.x ) + floor( gl_FragCoord.y ), 2.0 ) < 0.5 ) discard;`,
    );
  };
  material.customProgramCacheKey = () => "translucent-shadow";
  return material;
}
