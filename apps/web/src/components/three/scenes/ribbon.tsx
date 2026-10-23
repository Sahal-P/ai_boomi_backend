"use client";

import { useFrame } from "@react-three/fiber";
import { useReducedMotion } from "motion/react";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";

import { gsap, useGSAP } from "@/components/motion/gsap";

import { useCoinGeometry } from "../lib/assets";
import { createGold } from "../lib/materials";
import { useOwnReflections } from "../lib/use-reflections";

type Vec3 = readonly [number, number, number];

const PATH: readonly Vec3[] = [
  [-8, -1.3, -0.9],
  [-5.2, 0.15, 0.3],
  [-2.6, -0.45, 0.85],
  [0, 0.5, 0.2],
  [2.5, -0.35, -0.45],
  [5, 0.55, 0.35],
  [8, -0.7, -0.6],
];
const WIDTH = 1.05;
const THICKNESS = 0.08;
const SEGMENTS = 520;
const SAMPLES = 900;
const COIN_RADIUS = 0.25;
const COINS = 3;
const STOPS = ["#c7b6ff", "#efb2ff", "#ffa9d8", "#b59cff"].map((color) => new THREE.Color(color));
const UP = new THREE.Vector3(0, 1, 0);
const Z_AXIS = new THREE.Vector3(0, 0, 1);

/** Twist (radians) along the ribbon, 0–1: two slow half-turns that reveal edge and underside. */
function twist(u: number): number {
  return 0.95 * Math.sin(u * Math.PI * 2.1 + 0.4);
}

function gradientAt(u: number, target: THREE.Color): THREE.Color {
  const scaled = u * (STOPS.length - 1);
  const index = Math.min(Math.floor(scaled), STOPS.length - 2);
  const from = STOPS[index];
  const to = STOPS[index + 1];
  if (!from || !to) return target.set("#ffffff");
  return target.copy(from).lerp(to, scaled - index);
}

/** Rounded-rectangle cross-section (x across the ribbon, y through it) with outward normals. */
function ribbonProfile(steps = 5): Array<{ x: number; y: number; nx: number; ny: number }> {
  const radius = THICKNESS / 2;
  const half = WIDTH / 2 - radius;
  const points: Array<{ x: number; y: number; nx: number; ny: number }> = [];
  for (const [cx, start] of [
    [half, -Math.PI / 2],
    [-half, Math.PI / 2],
  ] as const) {
    for (let k = 0; k <= steps * 2; k += 1) {
      const angle = start + (Math.PI * k) / (steps * 2);
      points.push({ x: cx + radius * Math.cos(angle), y: radius * Math.sin(angle), nx: Math.cos(angle), ny: Math.sin(angle) });
    }
  }
  return points;
}

type Frame = { centre: THREE.Vector3; tangent: THREE.Vector3; up: THREE.Vector3; side: THREE.Vector3 };

/**
 * A glossy pastel ribbon sweeping across the call to action, twisting to catch the light,
 * with gold coins riding its surface through every twist. Coins speed up on descents and
 * ease over crests, so the stream never feels mechanical.
 */
export function RibbonScene() {
  const reduced = useReducedMotion() ?? false;
  const curve = useMemo(
    () => new THREE.CatmullRomCurve3(PATH.map(([x, y, z]) => new THREE.Vector3(x, y, z)), false, "centripetal", 0.5),
    [],
  );

  const frameAt = useMemo(() => {
    const tangent = new THREE.Vector3();
    const untwisted = new THREE.Vector3();
    return (u: number, target: Frame): Frame => {
      curve.getPointAt(u, target.centre);
      curve.getTangentAt(u, tangent).normalize();
      target.tangent.copy(tangent);
      untwisted.copy(UP).addScaledVector(tangent, -tangent.y).normalize();
      target.side.crossVectors(tangent, untwisted).normalize();
      const angle = twist(u);
      target.up.copy(untwisted).multiplyScalar(Math.cos(angle)).addScaledVector(target.side, Math.sin(angle));
      target.side.multiplyScalar(Math.cos(angle)).addScaledVector(untwisted, -Math.sin(angle));
      return target;
    };
  }, [curve]);

  const geometry = useMemo(() => {
    const profile = ribbonProfile();
    const ring = profile.length;
    const positions = new Float32Array((SEGMENTS + 1) * ring * 3);
    const normals = new Float32Array((SEGMENTS + 1) * ring * 3);
    const colors = new Float32Array((SEGMENTS + 1) * ring * 3);
    const frame: Frame = { centre: new THREE.Vector3(), tangent: new THREE.Vector3(), up: new THREE.Vector3(), side: new THREE.Vector3() };
    const point = new THREE.Vector3();
    const color = new THREE.Color();
    for (let i = 0; i <= SEGMENTS; i += 1) {
      const u = i / SEGMENTS;
      frameAt(u, frame);
      gradientAt(u, color);
      profile.forEach(({ x, y, nx, ny }, j) => {
        const offset = (i * ring + j) * 3;
        point.copy(frame.centre).addScaledVector(frame.side, x).addScaledVector(frame.up, y).toArray(positions, offset);
        point.copy(frame.side).multiplyScalar(nx).addScaledVector(frame.up, ny).toArray(normals, offset);
        color.toArray(colors, offset);
      });
    }
    const indices: number[] = [];
    for (let i = 0; i < SEGMENTS; i += 1) {
      for (let j = 0; j < ring; j += 1) {
        const a = i * ring + j;
        const b = i * ring + ((j + 1) % ring);
        const c = (i + 1) * ring + ((j + 1) % ring);
        const d = (i + 1) * ring + j;
        indices.push(a, d, b, b, d, c);
      }
    }
    const result = new THREE.BufferGeometry();
    result.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    result.setAttribute("normal", new THREE.BufferAttribute(normals, 3));
    result.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    result.setIndex(indices);
    result.computeBoundingSphere();
    return result;
  }, [frameAt]);

  // Time → arc length: speed rises as the ribbon falls (and eases over crests).
  const travel = useMemo(() => {
    const heights = Array.from({ length: SAMPLES }, (_, index) => curve.getPointAt(index / (SAMPLES - 1)).y);
    const top = Math.max(...heights);
    const step = curve.getLength() / (SAMPLES - 1);
    const times = new Float32Array(SAMPLES);
    let previous = 0;
    heights.forEach((height, index) => {
      const speed = Math.sqrt(0.55 + 1.6 * (top - height));
      if (index > 0) times[index] = (times[index - 1] ?? 0) + (2 * step) / (previous + speed);
      previous = speed;
    });
    return { times, duration: times[SAMPLES - 1] ?? 1, step };
  }, [curve]);

  const material = useMemo(
    () =>
      new THREE.MeshPhysicalMaterial({
        vertexColors: true,
        roughness: 0.2,
        clearcoat: 1,
        clearcoatRoughness: 0.07,
        sheen: 0.7,
        sheenColor: new THREE.Color("#ffe1f5"),
        sheenRoughness: 0.35,
        iridescence: 0.35,
        iridescenceIOR: 1.3,
      }),
    [],
  );
  const coin = useCoinGeometry("lite");
  const gold = useMemo(() => createGold(0.2), []);
  const coins = useRef<Array<THREE.Mesh | null>>([]);
  const group = useRef<THREE.Group>(null);
  const scratch = useMemo(
    () => ({
      frame: { centre: new THREE.Vector3(), tangent: new THREE.Vector3(), up: new THREE.Vector3(), side: new THREE.Vector3() } as Frame,
      face: new THREE.Vector3(),
      basis: new THREE.Matrix4(),
      roll: new THREE.Quaternion(),
    }),
    [],
  );
  useOwnReflections([material, gold]);
  useEffect(
    () => () => {
      geometry.dispose();
      material.dispose();
      gold.dispose();
    },
    [geometry, material, gold],
  );

  useGSAP(
    () => {
      if (reduced || !group.current) return;
      gsap.fromTo(group.current.position, { y: -0.06 }, { y: 0.06, duration: 4.6, ease: "sine.inOut", yoyo: true, repeat: -1 });
    },
    { dependencies: [reduced] },
  );

  useFrame((state) => {
    const time = reduced ? 3 : state.clock.elapsedTime;
    const period = travel.duration + 0.8;
    coins.current.forEach((mesh, index) => {
      if (!mesh) return;
      const seconds = (((time + (index * period) / COINS) % period) + period) % period;
      mesh.visible = seconds <= travel.duration;
      if (!mesh.visible) return;
      let lo = 0;
      let hi = SAMPLES - 1;
      while (hi - lo > 1) {
        const mid = (lo + hi) >> 1;
        if ((travel.times[mid] ?? 0) <= seconds) lo = mid;
        else hi = mid;
      }
      const t0 = travel.times[lo] ?? 0;
      const t1 = travel.times[hi] ?? 0;
      const sample = lo + (t1 > t0 ? (seconds - t0) / (t1 - t0) : 0);
      const { frame, face, basis, roll } = scratch;
      frameAt(sample / (SAMPLES - 1), frame);
      mesh.position.copy(frame.centre).addScaledVector(frame.up, THICKNESS / 2 + COIN_RADIUS);
      face.crossVectors(frame.tangent, frame.up);
      basis.makeBasis(frame.tangent, frame.up, face);
      mesh.quaternion.setFromRotationMatrix(basis).multiply(roll.setFromAxisAngle(Z_AXIS, -(sample * travel.step) / COIN_RADIUS));
    });
  });

  return (
    <group ref={group} rotation={[0.2, -0.1, 0.03]}>
      <mesh geometry={geometry} material={material} />
      {Array.from({ length: COINS }, (_, index) => (
        <mesh
          key={index}
          ref={(mesh) => {
            coins.current[index] = mesh;
          }}
          geometry={coin}
          material={gold}
          scale={COIN_RADIUS}
        />
      ))}
    </group>
  );
}
