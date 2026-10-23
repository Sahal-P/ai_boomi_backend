"use client";

import { useReducedMotion } from "motion/react";
import { useEffect, useMemo, useRef } from "react";
import type * as THREE from "three";

import { gsap, useGSAP } from "@/components/motion/gsap";

import { useDomeGeometry } from "../lib/assets";
import { createIridescentChrome } from "../lib/materials";
import { useOwnReflections } from "../lib/use-reflections";

/**
 * The verification dome — "every rupee verified". Sculpted chrome (filleted lip, rim bead,
 * check-outline ridge) with an interference film, turning on two sine yoyos of unrelated
 * lengths so its reflections sweep continuously without a visible loop.
 */
export function CheckOrbScene() {
  const reduced = useReducedMotion() ?? false;
  const geometry = useDomeGeometry();
  const material = useMemo(() => createIridescentChrome("#7d55ff", 0.08), []);
  const turn = useRef<THREE.Group>(null);
  const bob = useRef<THREE.Group>(null);
  useOwnReflections([material]);
  useEffect(() => () => material.dispose(), [material]);

  useGSAP(
    () => {
      if (reduced || !turn.current || !bob.current) return;
      const loop = { ease: "sine.inOut", yoyo: true, repeat: -1 } as const;
      // Face (+Z) turned ~45° up and to the left of the camera, as in the product reference,
      // so the hemisphere, the lip fillet and the rim bead all read.
      gsap.fromTo(turn.current.rotation, { y: -0.78 }, { y: -0.34, duration: 5.6, ...loop });
      gsap.fromTo(turn.current.rotation, { x: -0.98 }, { x: -0.7, duration: 4.3, ...loop });
      gsap.fromTo(bob.current.position, { y: -0.05 }, { y: 0.05, duration: 3.1, ...loop });
    },
    { dependencies: [reduced] },
  );

  return (
    <group ref={bob}>
      <group ref={turn} rotation={[-0.84, -0.56, -0.2]}>
        <mesh geometry={geometry} material={material} scale={0.94} />
      </group>
    </group>
  );
}
