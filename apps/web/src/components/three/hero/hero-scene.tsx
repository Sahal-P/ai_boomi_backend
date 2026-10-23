"use client";

import { RoundedBox } from "@react-three/drei";
import { useFrame, useThree } from "@react-three/fiber";
import { easing } from "maath";
import { useEffect, useMemo, useRef, type RefObject } from "react";
import * as THREE from "three";

import { gsap, useGSAP } from "@/components/motion/gsap";

import { useCoinGeometry } from "../lib/assets";
import { createFrostedAcrylic, createGold, createNeon } from "../lib/materials";
import type { QualityTier } from "../lib/quality";
import { createTranslucentShadowMaterial } from "../lib/soft-shadows";
import { createFloorTexture, createWindowGoboTexture, FLOOR_TEXTURE_SPAN } from "../lib/textures";
import { preToneMapped } from "../lib/tone";
import { useOwnReflections } from "../lib/use-reflections";
import { HeroSkyEnvironment } from "../studio-environment";
import { applyFloorSpill, createSpillUniforms, slabEmitterCorners, SPILL_EMITTERS } from "./floor-spill";
import { createTrack, type CoinPose, type Vec3 } from "./track";

export type HeroPointer = { x: number; y: number };

type HeroSceneProps = {
  quality: QualityTier;
  reducedMotion: boolean;
  pointer: RefObject<HeroPointer>;
  /** Hero scroll-out progress, 0 at rest → 1 when the section has left the viewport. */
  progress: RefObject<number>;
  onReady: () => void;
};

/** The hero section's CSS background; the canvas clears and fogs to exactly this colour. */
export const HERO_BACKGROUND = "#efedf6";
const CLEAR = preToneMapped(HERO_BACKGROUND);

// ---------------------------------------------------------------------------------- layout
// World axes are authored for the resting camera: +x screen-right, -z into the screen.

const SLAB_YAW = -0.42;
const CHANNEL_RADIUS = 0.38;
const COIN_RADIUS = 0.27;
const COINS = 3;
const COIN_GAP_SECONDS = 1.6;

/** `glow` is the LED colour; `spill` scales its floor light (saturated violet reads heavier). */
type SlabSpec = { position: Vec3; size: Vec3; glow?: string; spill?: number };

const SLABS: readonly SlabSpec[] = [
  { position: [0, 0.55, 0], size: [4.4, 0.3, 4.4], glow: "#ff4bd2", spill: 1 },
  { position: [4.4, 1.45, -4.8], size: [4.2, 0.3, 4.2], glow: "#8e5bff", spill: 0.34 },
  { position: [4.9, 0.2, 3.6], size: [3.8, 0.28, 3.6], glow: "#d63af9", spill: 0.8 },
  // Background layer: far back, softened by fog, behind the action rather than the copy.
  { position: [9.6, 0.3, -9.5], size: [4.6, 0.28, 4.6] },
  { position: [1.8, 2.7, -12.5], size: [5, 0.3, 5] },
];

/**
 * Channel centreline (resting heights = surface + channel radius): drops in from above the
 * back slab, S-curves down across the focal slab, and leaves over the front slab.
 */
const TRACK: readonly Vec3[] = [
  [2.4, 6.3, -12.5],
  [3.4, 3.7, -8.8],
  [4.1, 2.0, -6.2],
  [3.6, 1.98, -4.4],
  [2.3, 1.8, -3.1],
  [1.0, 1.27, -2.2],
  [-0.5, 1.08, -1.5],
  [-1.5, 1.08, -0.1],
  [-0.9, 1.08, 1.35],
  [0.7, 1.08, 1.55],
  [1.6, 1.08, 0.4],
  [2.6, 0.91, 1.4],
  [3.6, 0.72, 2.6],
  [5.0, 0.72, 3.5],
  [6.4, 0.55, 4.6],
  [8.5, 0.38, 6.6],
  [11, 0.38, 9],
];

/** Toward the sun: high, behind-left, so long shadows fall toward the viewer's right. */
const SUN_DIRECTION = new THREE.Vector3(-0.55, 0.72, -0.42).normalize();
const SUN_TARGET = new THREE.Vector3(1.2, 0, -0.6);
/** Direct sun (no distance falloff); the sky fill sits well below it so window shafts read. */
const SUN_INTENSITY = 17;
const LED_STRENGTH = 14;
/** Radiance of a slab's lit underside, as seen by the floor. */
const SPILL_RADIANCE = 5.5;

/** The LED undersides that light the floor, from the glowing slabs. */
const EMITTERS = SLABS.filter((spec) => spec.glow)
  .slice(0, SPILL_EMITTERS)
  .map((spec) => {
    const [x, y, z] = spec.position;
    const [width, height, depth] = spec.size;
    return {
      corners: slabEmitterCorners([x, y - height / 2 - 0.03, z], width * 0.84, depth * 0.84, SLAB_YAW),
      radiance: new THREE.Color(spec.glow).multiplyScalar(SPILL_RADIANCE * (spec.spill ?? 1)),
    };
  });

type Frame = {
  target: Vec3;
  azimuth: number;
  elevation: number;
  distance: number;
  fov: number;
  /** Lens shift as a fraction of the frame (keeps perspective, moves the subject). */
  shift: readonly [number, number];
};

const LANDSCAPE: Frame = { target: [2.1, 0.6, -1.0], azimuth: 0.14, elevation: 0.84, distance: 23.5, fov: 32, shift: [0.18, 0.01] };
const PORTRAIT: Frame = { target: [1.1, 0.5, -0.2], azimuth: 0.18, elevation: 0.92, distance: 25, fov: 38, shift: [0.04, -0.26] };

const easeScroll = gsap.parseEase("power2.inOut");
const TAU = Math.PI * 2;
/**
 * Sun shadow map size and tent half-width in texels (lib/soft-shadows.ts): penumbrae of
 * σ ≈ 2.4 cm (high) and 3.6 cm, free of texel stair-steps. High costs 16 taps a pixel.
 */
const SUN_SHADOW: Record<QualityTier, { size: number; radius: number }> = {
  high: { size: 2048, radius: 4 },
  medium: { size: 1024, radius: 3 },
  low: { size: 1024, radius: 3 },
};

// ------------------------------------------------------------------------- shared motion

/** Values GSAP tweens and the frame loop reads; nothing here triggers React renders. */
type Motion = {
  /** Coin clock (seconds) and its rate; the intro eases the rate up from rest. */
  clock: number;
  rate: number;
  /** Intro offsets that settle to 0. */
  dolly: number;
  crane: number;
  orbit: number;
  /** Light levels 0–1. */
  glow: number;
  sun: number;
};

// --------------------------------------------------------------------------------- pieces

/** Honed terrazzo floor, lit by the sun, the sky and the slabs' LED underglow. */
function Floor({ quality, motion }: { quality: QualityTier; motion: RefObject<Motion> }) {
  const maxAnisotropy = useThree((state) => state.gl.capabilities.getMaxAnisotropy());
  const spill = useMemo(() => {
    const uniforms = createSpillUniforms();
    EMITTERS.forEach((emitter, index) =>
      emitter.corners.forEach((corner, k) => uniforms.uSpillCorners.value[index * 4 + k]?.copy(corner)),
    );
    return uniforms;
  }, []);
  const material = useMemo(() => {
    const map = createFloorTexture(quality === "low" ? 1024 : 2048);
    map.anisotropy = Math.min(maxAnisotropy, 8);
    map.repeat.setScalar(140 / FLOOR_TEXTURE_SPAN);
    const floor = new THREE.MeshStandardMaterial({ color: "#ebe6f6", roughness: 0.5, map });
    applyFloorSpill(floor, spill);
    return floor;
  }, [quality, maxAnisotropy, spill]);
  useEffect(
    () => () => {
      material.map?.dispose();
      material.dispose();
    },
    [material],
  );
  useFrame(() => {
    const level = motion.current?.glow ?? 1;
    EMITTERS.forEach((emitter, index) => spill.uSpillRadiance.value[index]?.copy(emitter.radiance).multiplyScalar(level));
  });
  return (
    <mesh rotation-x={-Math.PI / 2} material={material} receiveShadow>
      <planeGeometry args={[140, 140]} />
    </mesh>
  );
}

/** Rounded-rectangle LED ring at the slab's underside edge: a hot line shows below the rim. */
function createStripGeometry(width: number, depth: number): THREE.BufferGeometry {
  const outer = new THREE.Shape();
  const inset = 0.035;
  const band = 0.035;
  const roundRect = (path: THREE.Path, w: number, d: number, r: number) => {
    path.moveTo(-w / 2 + r, -d / 2);
    path.lineTo(w / 2 - r, -d / 2);
    path.quadraticCurveTo(w / 2, -d / 2, w / 2, -d / 2 + r);
    path.lineTo(w / 2, d / 2 - r);
    path.quadraticCurveTo(w / 2, d / 2, w / 2 - r, d / 2);
    path.lineTo(-w / 2 + r, d / 2);
    path.quadraticCurveTo(-w / 2, d / 2, -w / 2, d / 2 - r);
    path.lineTo(-w / 2, -d / 2 + r);
    path.quadraticCurveTo(-w / 2, -d / 2, -w / 2 + r, -d / 2);
  };
  roundRect(outer, width - inset * 2, depth - inset * 2, 0.18);
  const hole = new THREE.Path();
  roundRect(hole, width - (inset + band) * 2, depth - (inset + band) * 2, 0.14);
  outer.holes.push(hole);
  const geometry = new THREE.ShapeGeometry(outer, 6);
  geometry.rotateX(Math.PI / 2);
  return geometry;
}

type SlabProps = { spec: SlabSpec; material: THREE.Material; motion: RefObject<Motion> };

/** A floating slab; glowing ones carry an HDR LED ring under the rim (their floor light is in Floor). */
function Slab({ spec, material, motion }: SlabProps) {
  const [width, height, depth] = spec.size;
  const strip = useMemo(() => createStripGeometry(width, depth), [width, depth]);
  const glowColor = useMemo(() => new THREE.Color(spec.glow ?? "#ffffff"), [spec.glow]);
  const neon = useMemo(() => createNeon(glowColor, LED_STRENGTH), [glowColor]);
  const strips = useRef<THREE.Mesh>(null);
  useEffect(
    () => () => {
      strip.dispose();
      neon.dispose();
    },
    [strip, neon],
  );

  useFrame(() => {
    const stripMaterial = strips.current?.material;
    if (stripMaterial instanceof THREE.MeshBasicMaterial) {
      stripMaterial.color.copy(glowColor).multiplyScalar(LED_STRENGTH * (motion.current?.glow ?? 1));
    }
  });

  return (
    <group position={spec.position} rotation-y={SLAB_YAW}>
      <RoundedBox args={[width, height, depth]} radius={0.045} smoothness={4} material={material} castShadow receiveShadow />
      {spec.glow ? <mesh ref={strips} geometry={strip} material={neon} position-y={-height / 2 - 0.006} /> : null}
    </group>
  );
}

function Channel({ quality, track }: { quality: QualityTier; track: ReturnType<typeof createTrack> }) {
  const geometry = useMemo(
    () => track.createGeometry(quality === "high" ? 720 : quality === "medium" ? 480 : 320, quality === "low" ? 16 : 26),
    [quality, track],
  );
  const material = useMemo(() => createFrostedAcrylic(quality), [quality]);
  const shadowMaterial = useMemo(() => createTranslucentShadowMaterial(), []);
  useOwnReflections([material]);
  useEffect(
    () => () => {
      geometry.dispose();
      material.dispose();
    },
    [geometry, material],
  );
  useEffect(() => () => shadowMaterial.dispose(), [shadowMaterial]);
  return <mesh geometry={geometry} material={material} customDepthMaterial={shadowMaterial} castShadow receiveShadow />;
}

const pose: CoinPose = { position: new THREE.Vector3(), quaternion: new THREE.Quaternion() };

function RollingCoins({ track, motion }: { track: ReturnType<typeof createTrack>; motion: RefObject<Motion> }) {
  const geometry = useCoinGeometry("lite");
  const material = useMemo(() => createGold(), []);
  const coins = useRef<Array<THREE.Mesh | null>>([]);
  useOwnReflections([material]);
  useEffect(() => () => material.dispose(), [material]);

  useFrame(() => {
    const period = track.duration + COIN_GAP_SECONDS;
    const clock = motion.current?.clock ?? 0;
    coins.current.forEach((coin, index) => {
      if (!coin) return;
      const seconds = (((clock - (index * period) / COINS) % period) + period) % period;
      coin.visible = track.poseAt(seconds, pose);
      coin.position.copy(pose.position);
      coin.quaternion.copy(pose.quaternion);
    });
  });

  return (
    <>
      {Array.from({ length: COINS }, (_, index) => (
        <mesh
          key={index}
          ref={(mesh) => {
            coins.current[index] = mesh;
          }}
          geometry={geometry}
          material={material}
          scale={COIN_RADIUS}
          castShadow
          receiveShadow
        />
      ))}
    </>
  );
}

/**
 * Warm sun through a large window: a distant, narrow spot light projecting the window gobo.
 * Its aim wanders on a slow Lissajous (70 s / 90 s), so the shafts drift across the set
 * like late-afternoon light rather than sitting painted on the floor.
 */
function Sun({ quality, motion, reducedMotion }: { quality: QualityTier; motion: RefObject<Motion>; reducedMotion: boolean }) {
  const light = useRef<THREE.SpotLight>(null);
  const gobo = useMemo(() => createWindowGoboTexture(), []);
  const aim = useMemo(() => new THREE.Object3D(), []);
  const position = useMemo(() => SUN_TARGET.clone().addScaledVector(SUN_DIRECTION, 36), []);
  useEffect(() => () => gobo.dispose(), [gobo]);
  useFrame((state) => {
    if (light.current) light.current.intensity = SUN_INTENSITY * (motion.current?.sun ?? 1);
    const time = reducedMotion ? 0 : state.clock.elapsedTime;
    aim.position.set(
      SUN_TARGET.x + Math.sin((TAU * time) / 70) * 0.9,
      SUN_TARGET.y,
      SUN_TARGET.z + Math.sin((TAU * time) / 90 + 1.1) * 0.7,
    );
  });
  const shadow = SUN_SHADOW[quality];
  return (
    <>
      <primitive object={aim} />
      {/* Keyed by tier: three allocates a shadow map once, so a new size needs a new light. */}
      <spotLight
        key={quality}
        ref={light}
        position={position}
        target={aim}
        map={gobo}
        angle={0.4}
        penumbra={0.65}
        decay={0}
        intensity={SUN_INTENSITY}
        color="#ffeedb"
        castShadow
        shadow-mapSize={[shadow.size, shadow.size]}
        shadow-radius={shadow.radius}
        shadow-bias={-0.0002}
        shadow-normalBias={0.025}
        shadow-camera-near={20}
        shadow-camera-far={60}
      />
    </>
  );
}

type RigProps = Pick<HeroSceneProps, "pointer" | "progress" | "reducedMotion"> & { motion: RefObject<Motion> };

/**
 * Orbit rig composed in layers: resting frame (per aspect) + GSAP intro offsets + scroll
 * push-in + slow idle drift (incommensurate periods, never visibly loops) + damped pointer
 * parallax. Everything is critically damped against frame time, so it is rate independent.
 */
function CameraRig({ pointer, progress, reducedMotion, motion }: RigProps) {
  const smoothed = useRef(new THREE.Vector2());
  const look = useRef(new THREE.Vector3());
  const shift = useRef({ x: Number.NaN, y: Number.NaN });

  useFrame((state, delta) => {
    const camera = state.camera;
    if (!(camera instanceof THREE.PerspectiveCamera)) return;
    const frame = state.size.width / Math.max(state.size.height, 1) < 0.95 ? PORTRAIT : LANDSCAPE;
    const live = reducedMotion ? 0 : 1;
    const time = state.clock.elapsedTime;
    const intro = motion.current;
    const scroll = easeScroll(Math.min(Math.max(progress.current ?? 0, 0), 1));
    const target = pointer.current ?? { x: 0, y: 0 };
    easing.damp2(smoothed.current, [target.x * live, target.y * live], 0.85, delta);

    const azimuth =
      frame.azimuth + (intro?.orbit ?? 0) + live * 0.065 * Math.sin((TAU * time) / 41) + smoothed.current.x * 0.06 + scroll * 0.2;
    const elevation =
      frame.elevation +
      (intro?.crane ?? 0) +
      live * 0.028 * Math.sin((TAU * time) / 29 + 1.3) -
      smoothed.current.y * 0.035 +
      scroll * 0.24;
    const distance =
      frame.distance * (1 + (intro?.dolly ?? 0) - scroll * 0.24) + live * 0.22 * Math.sin((TAU * time) / 35 + 0.4);

    look.current.set(frame.target[0], frame.target[1] - scroll * 0.35, frame.target[2] - scroll * 1.1);
    camera.position.set(
      look.current.x + Math.sin(azimuth) * Math.cos(elevation) * distance,
      look.current.y + Math.sin(elevation) * distance,
      look.current.z + Math.cos(azimuth) * Math.cos(elevation) * distance,
    );
    camera.lookAt(look.current);

    if (camera.fov !== frame.fov || shift.current.x !== frame.shift[0] || shift.current.y !== frame.shift[1]) {
      camera.fov = frame.fov;
      shift.current = { x: frame.shift[0], y: frame.shift[1] };
      // Unit "full size" view offset = resolution-independent lens shift.
      camera.setViewOffset(1, 1, -frame.shift[0], frame.shift[1], 1, 1);
      camera.updateProjectionMatrix();
    }
  });
  return null;
}

export function HeroScene({ quality, reducedMotion, pointer, progress, onReady }: HeroSceneProps) {
  const track = useMemo(
    () =>
      createTrack({
        points: TRACK,
        outerRadius: CHANNEL_RADIUS,
        wall: 0.07,
        coinRadius: COIN_RADIUS,
        gravity: 1.4,
        drag: 0.32,
        entrySpeed: 1.1,
        minSpeed: 0.75,
        bank: 0.7,
      }),
    [],
  );
  const slabMaterial = useMemo(() => new THREE.MeshStandardMaterial({ color: "#fbf9ff", roughness: 0.66 }), []);
  useEffect(() => () => slabMaterial.dispose(), [slabMaterial]);

  // Coins start mid-journey (clock 7 s) so the first frame is already composed.
  const motion = useRef<Motion>({ clock: 7, rate: 1, dolly: 0, crane: 0, orbit: 0, glow: 1, sun: 1 });
  // The frosted channel is the only transmissive surface and its blur hides a half- or
  // smaller-resolution buffer; the full-size pass re-shaded the whole floor (~8 fps).
  const transmissionScale = quality === "high" ? 0.5 : 0.4;

  useEffect(onReady, [onReady]);

  useGSAP(
    () => {
      if (reducedMotion) return;
      const state = motion.current;
      gsap
        .timeline({ defaults: { ease: "power3.inOut" } })
        .fromTo(state, { dolly: 0.3, crane: 0.16, orbit: -0.24 }, { dolly: 0, crane: 0, orbit: 0, duration: 3.6 }, 0)
        .fromTo(state, { sun: 0.45, glow: 0 }, { sun: 1, glow: 1, duration: 2.8, ease: "power2.inOut" }, 0.35)
        .fromTo(state, { rate: 0 }, { rate: 1, duration: 2.4, ease: "power2.in" }, 0.8);
    },
    { dependencies: [reducedMotion] },
  );

  useFrame(({ gl }, delta) => {
    const state = motion.current;
    if (!reducedMotion) state.clock += Math.min(delta, 0.1) * state.rate;
    if (gl.transmissionResolutionScale !== transmissionScale) gl.transmissionResolutionScale = transmissionScale;
  });

  return (
    <>
      <color attach="background" args={[CLEAR]} />
      <fog attach="fog" args={[CLEAR, 24, 66]} />
      <HeroSkyEnvironment sunDirection={SUN_DIRECTION} />
      <Sun quality={quality} motion={motion} reducedMotion={reducedMotion} />
      <CameraRig pointer={pointer} progress={progress} reducedMotion={reducedMotion} motion={motion} />

      <Floor quality={quality} motion={motion} />
      {SLABS.map((spec, index) => (
        <Slab key={index} spec={spec} material={slabMaterial} motion={motion} />
      ))}
      <Channel quality={quality} track={track} />
      <RollingCoins track={track} motion={motion} />
    </>
  );
}
