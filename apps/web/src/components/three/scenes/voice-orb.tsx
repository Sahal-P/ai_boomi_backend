"use client";

import { useFrame } from "@react-three/fiber";
import { useReducedMotion } from "motion/react";
import { useEffect, useMemo, useRef, type RefObject } from "react";
import * as THREE from "three";

import { gsap, useGSAP } from "@/components/motion/gsap";

import { createGlass } from "../lib/materials";
import { useQualityTier } from "../lib/quality";
import { preToneMapped } from "../lib/tone";
import { useOwnReflections } from "../lib/use-reflections";
import type { VoiceOrbState } from "../scene-spec";

/** The page canvas colour behind the orb (globals.css `--canvas`). */
const PAGE = "#f5f4fb";

type Palette = { deep: string; mid: string; hot: string; swirl: number; energy: number };

/** Luminous centre (`deep`) → halo (`mid`) → pale rim (`hot`). */
const PALETTES: Record<VoiceOrbState, Palette> = {
  idle: { deep: "#3d5bff", mid: "#8d8cff", hot: "#efeaff", swirl: 0, energy: 0.1 },
  listening: { deep: "#7a3cff", mid: "#d07cff", hot: "#ffe1f2", swirl: 0.35, energy: 0.35 },
  thinking: { deep: "#3446ff", mid: "#7f6dff", hot: "#e9e4ff", swirl: 1, energy: 0.25 },
  speaking: { deep: "#2f63ff", mid: "#8a7dff", hot: "#ffe4f4", swirl: 0.25, energy: 0.3 },
};

// 3D simplex noise: Ashima Arts / Stefan Gustavson (MIT).
const NOISE = /* glsl */ `
  vec3 mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
  vec4 mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
  vec4 permute(vec4 x) { return mod289(((x * 34.0) + 10.0) * x); }
  vec4 taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }
  float snoise(vec3 v) {
    const vec2 C = vec2(1.0 / 6.0, 1.0 / 3.0);
    const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);
    vec3 i = floor(v + dot(v, C.yyy));
    vec3 x0 = v - i + dot(i, C.xxx);
    vec3 g = step(x0.yzx, x0.xyz);
    vec3 l = 1.0 - g;
    vec3 i1 = min(g.xyz, l.zxy);
    vec3 i2 = max(g.xyz, l.zxy);
    vec3 x1 = x0 - i1 + C.xxx;
    vec3 x2 = x0 - i2 + C.yyy;
    vec3 x3 = x0 - D.yyy;
    i = mod289(i);
    vec4 p = permute(permute(permute(i.z + vec4(0.0, i1.z, i2.z, 1.0)) + i.y + vec4(0.0, i1.y, i2.y, 1.0)) + i.x + vec4(0.0, i1.x, i2.x, 1.0));
    float n_ = 0.142857142857;
    vec3 ns = n_ * D.wyz - D.xzx;
    vec4 j = p - 49.0 * floor(p * ns.z * ns.z);
    vec4 x_ = floor(j * ns.z);
    vec4 y_ = floor(j - 7.0 * x_);
    vec4 x = x_ * ns.x + ns.yyyy;
    vec4 y = y_ * ns.x + ns.yyyy;
    vec4 h = 1.0 - abs(x) - abs(y);
    vec4 b0 = vec4(x.xy, y.xy);
    vec4 b1 = vec4(x.zw, y.zw);
    vec4 s0 = floor(b0) * 2.0 + 1.0;
    vec4 s1 = floor(b1) * 2.0 + 1.0;
    vec4 sh = -step(h, vec4(0.0));
    vec4 a0 = b0.xzyw + s0.xzyw * sh.xxyy;
    vec4 a1 = b1.xzyw + s1.xzyw * sh.zzww;
    vec3 p0 = vec3(a0.xy, h.x);
    vec3 p1 = vec3(a0.zw, h.y);
    vec3 p2 = vec3(a1.xy, h.z);
    vec3 p3 = vec3(a1.zw, h.w);
    vec4 norm = taylorInvSqrt(vec4(dot(p0, p0), dot(p1, p1), dot(p2, p2), dot(p3, p3)));
    p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
    vec4 m = max(0.5 - vec4(dot(x0, x0), dot(x1, x1), dot(x2, x2), dot(x3, x3)), 0.0);
    m = m * m;
    return 105.0 * dot(m * m, vec4(dot(p0, x0), dot(p1, x1), dot(p2, x2), dot(p3, x3)));
  }
  float fbm(vec3 p) {
    float sum = 0.0;
    float amplitude = 0.5;
    for (int i = 0; i < 4; i++) {
      sum += amplitude * snoise(p);
      p = p * 2.03 + 11.7;
      amplitude *= 0.5;
    }
    return sum;
  }
`;

const coreVertex = /* glsl */ `
  uniform float uTime;
  uniform float uEnergy;
  varying vec3 vObject;
  varying vec3 vNormal;
  varying vec3 vView;
  ${NOISE}
  void main() {
    vec3 p = position;
    float breathe = fbm(normal * 0.9 + vec3(0.0, uTime * 0.3, 0.0));
    p += normal * breathe * (0.012 + uEnergy * 0.05);
    vObject = position;
    vec4 mv = modelViewMatrix * vec4(p, 1.0);
    vNormal = normalize(normalMatrix * normal);
    vView = normalize(-mv.xyz);
    gl_Position = projectionMatrix * mv;
  }
`;

const coreFragment = /* glsl */ `
  uniform float uTime;
  uniform float uEnergy;
  uniform float uSwirl;
  uniform vec3 uDeep;
  uniform vec3 uMid;
  uniform vec3 uHot;
  uniform vec3 uPage;
  varying vec3 vObject;
  varying vec3 vNormal;
  varying vec3 vView;
  ${NOISE}
  void main() {
    vec3 p = normalize(vObject);
    float t = uTime * (0.1 + uSwirl * 0.5);
    // Low-frequency, domain-warped flow: drifting light, not marbled smoke.
    float warp = fbm(p * 1.1 + vec3(t, -t * 0.6, t * 0.4));
    float n = fbm(p * 1.35 + warp * (0.7 + uEnergy * 0.8) + vec3(0.0, t, 0.0));
    float facing = clamp(dot(normalize(vNormal), normalize(vView)), 0.0, 1.0);
    // Light pooled in the centre, a lilac halo, a pale rim; the flow bends the boundaries.
    float centre = smoothstep(0.35, 1.0, facing + n * 0.3);
    vec3 color = mix(uMid * 0.9, uMid, smoothstep(0.0, 0.5, facing));
    color = mix(color, uDeep * 1.35, centre);
    color += uHot * smoothstep(0.3, 0.8, n) * 0.14 * facing;
    color *= 0.92 + uEnergy * 0.55;
    // Feather the silhouette into the page colour so the core reads as light, not a ball.
    color = mix(uPage, color, smoothstep(0.02, 0.5, facing));
    gl_FragColor = vec4(color, 1.0);
    #include <tonemapping_fragment>
    #include <colorspace_fragment>
  }
`;

type VoiceOrbSceneProps = { state?: VoiceOrbState; level?: RefObject<number> | undefined };

/**
 * The assistant: a dispersive glass sphere refracting a living plasma core (domain-warped
 * noise in the state's palette). State changes ease the palette and flow with GSAP; the
 * live voice level adds energy every frame.
 */
export function VoiceOrbScene({ state = "idle", level }: VoiceOrbSceneProps) {
  const quality = useQualityTier();
  const reduced = useReducedMotion() ?? false;
  const core = useMemo(
    () =>
      new THREE.ShaderMaterial({
        vertexShader: coreVertex,
        fragmentShader: coreFragment,
        uniforms: {
          uTime: { value: 0 },
          uEnergy: { value: 0 },
          uSwirl: { value: 0 },
          uDeep: { value: new THREE.Color(PALETTES.idle.deep) },
          uMid: { value: new THREE.Color(PALETTES.idle.mid) },
          uHot: { value: new THREE.Color(PALETTES.idle.hot) },
          // Pre-image under Neutral tone mapping, so the feathered edge lands exactly on --canvas.
          uPage: { value: preToneMapped(PAGE) },
        },
      }),
    [],
  );
  const shell = useMemo(
    () =>
      quality === "low"
        ? new THREE.MeshPhysicalMaterial({ color: "#ffffff", transparent: true, opacity: 0.18, roughness: 0.05, clearcoat: 1 })
        : createGlass({ roughness: 0.02, thickness: 0.9, dispersion: 0.3, tint: "#f2f0ff", absorption: 10 }),
    [quality],
  );
  // GSAP eases these plain values; the frame loop copies them into the core's uniforms.
  const backdrop = useMemo(() => new THREE.MeshBasicMaterial({ color: PAGE, toneMapped: false }), []);
  useEffect(() => () => backdrop.dispose(), [backdrop]);
  const tween = useRef({
    swirl: PALETTES.idle.swirl,
    energy: PALETTES.idle.energy,
    deep: new THREE.Color(PALETTES.idle.deep),
    mid: new THREE.Color(PALETTES.idle.mid),
    hot: new THREE.Color(PALETTES.idle.hot),
  });
  const coreMesh = useRef<THREE.Mesh>(null);
  useOwnReflections([shell]);
  useEffect(() => () => core.dispose(), [core]);
  useEffect(() => () => shell.dispose(), [shell]);

  useGSAP(
    () => {
      const palette = PALETTES[state];
      const current = tween.current;
      const duration = reduced ? 0 : 0.9;
      const ease = "power2.inOut";
      for (const [color, hex] of [
        [current.deep, palette.deep],
        [current.mid, palette.mid],
        [current.hot, palette.hot],
      ] as const) {
        const target = new THREE.Color(hex);
        gsap.to(color, { r: target.r, g: target.g, b: target.b, duration, ease });
      }
      gsap.to(current, { swirl: palette.swirl, energy: palette.energy, duration, ease });
    },
    { dependencies: [state, reduced] },
  );

  useFrame((frame) => {
    const material = coreMesh.current?.material;
    if (!(material instanceof THREE.ShaderMaterial)) return;
    const { uTime, uSwirl, uEnergy, uDeep, uMid, uHot } = material.uniforms;
    const current = tween.current;
    if (uTime) uTime.value = reduced ? 4 : frame.clock.elapsedTime;
    if (uSwirl) uSwirl.value = current.swirl;
    if (uEnergy) uEnergy.value = Math.max(current.energy, (level?.current ?? 0) * 0.85);
    if (uDeep?.value instanceof THREE.Color) uDeep.value.copy(current.deep);
    if (uMid?.value instanceof THREE.Color) uMid.value.copy(current.mid);
    if (uHot?.value instanceof THREE.Color) uHot.value.copy(current.hot);
  });

  return (
    <group>
      <mesh ref={coreMesh} material={core}>
        <icosahedronGeometry args={[0.44, 32]} />
      </mesh>
      <mesh material={shell}>
        <sphereGeometry args={[1, 96, 64]} />
      </mesh>
      {/* Something opaque for the glass to refract: the page colour, sized to stay hidden
          behind the sphere's silhouette (three otherwise refracts a 50% white clear). */}
      <mesh position-z={-1.05} material={backdrop}>
        <circleGeometry args={[1.18, 96]} />
      </mesh>
    </group>
  );
}
