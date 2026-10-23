"use client";

import { ContactShadows, RoundedBox } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useReducedMotion } from "motion/react";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";

import { gsap, useGSAP } from "@/components/motion/gsap";

import { useCoinGeometry } from "../lib/assets";
import { createAnodised, createGold, createSatinAcrylic } from "../lib/materials";
import { createRandom, randomBetween } from "../lib/random";
import { useOwnReflections } from "../lib/use-reflections";

const MAX_COINS = 16;
const SCALE = 0.31;
const STEP = 0.2 * SCALE * 1.025;
const COLUMN_GAP = 0.74;
const DROP = 2.4;
const PLATE_TOP = 0.06; // plate is 0.16 thick, centred 0.02 below the origin

type Placement = { column: number; x: number; y: number; twist: number; jitter: readonly [number, number]; gold: boolean };

/**
 * Cash-flow columns that are built when the card is revealed: coins drop in column by
 * column and settle (no bounce) on a frosted plate; first and last columns are gold
 * (money in / left), the middle anodised violet (committed). Heights are 0–1 values.
 */
export function CoinStackScene({ values, revealed }: { values: readonly number[]; revealed: boolean }) {
  const reduced = useReducedMotion() ?? false;
  const geometry = useCoinGeometry("lite");
  const materials = useMemo(() => ({ gold: createGold(0.21), violet: createAnodised("#9a7bff", 0.24) }), []);
  const plate = useMemo(() => createSatinAcrylic(), []);
  useOwnReflections([materials.gold, materials.violet, plate]);
  useEffect(() => () => Object.values(materials).forEach((material) => material.dispose()), [materials]);
  useEffect(() => () => plate.dispose(), [plate]);

  const placements = useMemo(() => {
    const random = createRandom(5);
    const list: Placement[] = [];
    values.forEach((value, column) => {
      const count = Math.max(1, Math.round(Math.min(1, Math.max(0, value)) * MAX_COINS));
      for (let index = 0; index < count; index += 1) {
        list.push({
          column,
          x: (column - (values.length - 1) / 2) * COLUMN_GAP,
          y: PLATE_TOP + STEP * (index + 0.5),
          twist: randomBetween(random, 0, Math.PI * 2),
          jitter: [randomBetween(random, -0.012, 0.012), randomBetween(random, -0.012, 0.012)],
          gold: column === 0 || column === values.length - 1,
        });
      }
    });
    return list;
  }, [values]);

  const drops = useRef<Array<{ p: number }>>([]);
  const gold = useRef<THREE.InstancedMesh>(null);
  const violet = useRef<THREE.InstancedMesh>(null);
  const group = useRef<THREE.Group>(null);
  const settled = useRef(false);

  useGSAP(
    () => {
      drops.current = placements.map(() => ({ p: reduced ? 1 : 0 }));
      settled.current = false;
      if (reduced || !revealed) return;
      gsap.to(drops.current, { p: 1, duration: 0.75, ease: "power3.out", stagger: 0.032, delay: 0.15 });
      if (group.current) {
        gsap.fromTo(group.current.rotation, { y: -0.16 }, { y: 0.12, duration: 7.5, ease: "sine.inOut", yoyo: true, repeat: -1 });
      }
    },
    { dependencies: [placements, revealed, reduced] },
  );

  const scratch = useMemo(
    () => ({
      matrix: new THREE.Matrix4(),
      position: new THREE.Vector3(),
      quaternion: new THREE.Quaternion(),
      euler: new THREE.Euler(),
      scale: new THREE.Vector3(SCALE, SCALE, SCALE),
    }),
    [],
  );

  useFrame(() => {
    if (settled.current) return;
    let goldIndex = 0;
    let violetIndex = 0;
    let moving = false;
    placements.forEach((placement, index) => {
      const p = drops.current[index]?.p ?? 0;
      if (p < 1) moving = true;
      scratch.position.set(placement.x + placement.jitter[0], placement.y + (1 - p) * DROP, placement.jitter[1]);
      scratch.quaternion.setFromEuler(scratch.euler.set(-Math.PI / 2, 0, placement.twist + (1 - p) * 1.4));
      scratch.matrix.compose(scratch.position, scratch.quaternion, scratch.scale);
      const mesh = placement.gold ? gold.current : violet.current;
      mesh?.setMatrixAt(placement.gold ? goldIndex++ : violetIndex++, scratch.matrix);
    });
    for (const [mesh, count] of [
      [gold.current, goldIndex],
      [violet.current, violetIndex],
    ] as const) {
      if (!mesh) continue;
      mesh.count = count;
      mesh.instanceMatrix.needsUpdate = true;
      mesh.computeBoundingSphere();
    }
    // Matrices are static once every coin has landed; stop re-uploading them.
    settled.current = !moving && drops.current.length === placements.length;
  });

  const width = values.length * COLUMN_GAP + 0.36;
  return (
    <group ref={group} position-y={-0.62}>
      <instancedMesh ref={gold} args={[geometry, materials.gold, placements.length]} frustumCulled={false} />
      <instancedMesh ref={violet} args={[geometry, materials.violet, placements.length]} frustumCulled={false} />
      <RoundedBox args={[width, 0.16, 1.15]} radius={0.06} smoothness={4} position-y={-0.02} material={plate} />
      <ContactShadows
        position-y={PLATE_TOP + 0.002}
        width={width}
        height={1.15}
        far={1.2}
        blur={1.6}
        opacity={0.55}
        resolution={256}
        color="#2a1d5c"
      />
    </group>
  );
}
