"use client";

import { ContactShadows, RoundedBox } from "@react-three/drei";
import { useFrame } from "@react-three/fiber";
import { useReducedMotion } from "motion/react";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";

import { gsap, useGSAP } from "@/components/motion/gsap";

import { useCoinGeometry } from "../lib/assets";
import { createNeon, createSunflower, createSurfaceGlass } from "../lib/materials";
import { useOwnReflections } from "../lib/use-reflections";

/**
 * A sunflower ₹ sealed in a glass block — "your data stays yours". The coin turns slowly inside
 * while the block sways on two unrelated sine yoyos; its bevels and inner faces carry the
 * studio's reflections, and a drawn ring and a contact shadow anchor it to the card.
 */
export function PrivacyVaultScene() {
  const reduced = useReducedMotion() ?? false;
  const coinGeometry = useCoinGeometry("full");
  const sunflower = useMemo(() => createSunflower(0.17), []);
  const glass = useMemo(() => createSurfaceGlass("#f2f6f8", 0.16), []);
  // An ink line, like the illustrations' line art, softened so it frames rather than outlines.
  const ring = useMemo(() => createNeon("#474b52", 1), []);
  const block = useRef<THREE.Group>(null);
  const coin = useRef<THREE.Mesh>(null);
  useOwnReflections([sunflower, glass]);
  useEffect(
    () => () => {
      sunflower.dispose();
      ring.dispose();
    },
    [sunflower, ring],
  );
  useEffect(() => () => glass.dispose(), [glass]);

  useGSAP(
    () => {
      if (reduced || !block.current) return;
      const loop = { ease: "sine.inOut", yoyo: true, repeat: -1 } as const;
      gsap.fromTo(block.current.rotation, { y: -0.82 }, { y: -0.36, duration: 6.4, ...loop });
      gsap.fromTo(block.current.rotation, { x: 0.1 }, { x: 0.24, duration: 5.1, ...loop });
      gsap.fromTo(block.current.position, { y: 0.04 }, { y: 0.12, duration: 3.7, ...loop });
    },
    { dependencies: [reduced] },
  );

  useFrame((state) => {
    if (!coin.current) return;
    const time = reduced ? 1.2 : state.clock.elapsedTime;
    coin.current.rotation.set(Math.sin(time * 0.6) * 0.12, time * 0.55, 0);
  });

  return (
    <group>
      <group ref={block} rotation={[0.16, -0.6, 0]} position-y={0.08}>
        <mesh ref={coin} geometry={coinGeometry} material={sunflower} scale={0.46} />
        <RoundedBox args={[1.55, 1.55, 1.55]} radius={0.24} smoothness={8} material={glass} />
      </group>
      <mesh material={ring} position-y={-1.02} rotation-x={Math.PI / 2}>
        <torusGeometry args={[1.12, 0.008, 12, 180]} />
      </mesh>
      <ContactShadows position-y={-1.06} scale={4} far={2.6} blur={3} opacity={0.26} resolution={256} color="#0e1013" />
    </group>
  );
}
