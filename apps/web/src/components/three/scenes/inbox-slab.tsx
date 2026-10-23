"use client";

import { RoundedBox } from "@react-three/drei";
import { useReducedMotion } from "motion/react";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";

import { gsap, useGSAP } from "@/components/motion/gsap";

import { useCoinGeometry } from "../lib/assets";
import { createGold, createNeon } from "../lib/materials";
import { useOwnReflections } from "../lib/use-reflections";

const COINS = 3;
const CYCLE = 4.2;
const TRAY = { width: 2.7, height: 0.34, depth: 1.75 } as const;
const SLOT = { width: 1.55, depth: 0.12 } as const;
const COIN_SCALE = 0.32;

/**
 * Connect Gmail: a satin acrylic inbox with a lit mail slot. Gold coins stay hidden inside
 * until they rise crisply through the slot — rim-lit violet as they clear it — turn half a
 * revolution and leave the frame, one after another in a continuous stream.
 */
export function InboxSlabScene() {
  const reduced = useReducedMotion() ?? false;
  const coin = useCoinGeometry("lite");
  const gold = useMemo(() => createGold(0.2), []);
  const tray = useMemo(
    () =>
      new THREE.MeshPhysicalMaterial({
        color: "#f6f2ff",
        roughness: 0.38,
        clearcoat: 0.7,
        clearcoatRoughness: 0.12,
        sheen: 0.4,
        sheenColor: new THREE.Color("#ffffff"),
      }),
    [],
  );
  const slotWell = useMemo(() => new THREE.MeshStandardMaterial({ color: "#1d1638", roughness: 0.6 }), []);
  const slotLight = useMemo(() => createNeon("#b46bff", 3.2), []);
  const coins = useRef<Array<THREE.Group | null>>([]);
  useOwnReflections([gold, tray]);
  useEffect(
    () => () => {
      [gold, tray, slotWell, slotLight].forEach((material) => material.dispose());
    },
    [gold, tray, slotWell, slotLight],
  );

  useGSAP(
    () => {
      coins.current.forEach((group, index) => {
        if (!group) return;
        const x = (index - (COINS - 1) / 2) * 0.42;
        // Rises from just under the slot (hidden by the tray) to out of frame; it only turns
        // once clear of the slot (~half way on the power2.in rise), so it never clips the lid.
        const turn = { duration: CYCLE / 2, ease: "power1.in" };
        const timeline = gsap
          .timeline({ repeat: -1, paused: reduced })
          .fromTo(group.position, { x, y: -0.2 }, { y: 2.7, duration: CYCLE, ease: "power2.in" }, 0)
          .fromTo(group.rotation, { y: 0 }, { y: Math.PI, ...turn }, CYCLE / 2)
          .fromTo(group.rotation, { z: 0 }, { z: index % 2 ? 0.22 : -0.22, ...turn }, CYCLE / 2);
        timeline.progress(((index + 0.3) / COINS) % 1);
      });
    },
    { dependencies: [reduced] },
  );

  const top = TRAY.height / 2;
  return (
    <group position-y={-0.7} rotation={[0.08, -0.32, 0]}>
      <RoundedBox args={[TRAY.width, TRAY.height, TRAY.depth]} radius={0.1} smoothness={5} material={tray} />
      {/* Recessed slot: a dark well with the light strip set just below the surface. */}
      <mesh material={slotWell} position-y={top - 0.025}>
        <boxGeometry args={[SLOT.width, 0.06, SLOT.depth]} />
      </mesh>
      <mesh material={slotLight} position-y={top - 0.004} rotation-x={-Math.PI / 2}>
        <planeGeometry args={[SLOT.width - 0.08, SLOT.depth * 0.45]} />
      </mesh>
      <pointLight position={[0, top + 0.25, 0.05]} color="#b46bff" intensity={2.6} distance={2.2} decay={2} />
      {Array.from({ length: COINS }, (_, index) => (
        <group
          key={index}
          ref={(group) => {
            coins.current[index] = group;
          }}
        >
          <mesh geometry={coin} material={gold} scale={COIN_SCALE} />
        </group>
      ))}
    </group>
  );
}
