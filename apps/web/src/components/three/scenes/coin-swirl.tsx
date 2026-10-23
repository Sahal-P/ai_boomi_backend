"use client";

import { useFrame } from "@react-three/fiber";
import { useReducedMotion } from "motion/react";
import { useEffect, useMemo, useRef } from "react";
import * as THREE from "three";

import { gsap, useGSAP } from "@/components/motion/gsap";

import { useCoinGeometry } from "../lib/assets";
import { createAnodised } from "../lib/materials";
import { createRandom, randomBetween } from "../lib/random";
import { useOwnReflections } from "../lib/use-reflections";

const COUNT = 12;
const RING = 1.18;
const SCALE = 0.4;
const ORBIT_SPEED = 0.3;
const STAGGER = 0.4;
const STACK_TILT = 0.36;
const STACK_STEP = 0.2 * SCALE * 1.03;
const TINTS = ["#ff4fb4", "#c34bff", "#ff7d9c"] as const;
const TAU = Math.PI * 2;
const RING_TILT = new THREE.Quaternion().setFromEuler(new THREE.Euler(-1.05, 0.12, -0.38));
const STACK_AXIS = new THREE.Vector3(0, Math.cos(STACK_TILT), Math.sin(STACK_TILT));
const FACE = new THREE.Vector3(0, 0, 1);
const easeMerge = gsap.parseEase("power3.inOut");

const scratch = {
  position: new THREE.Vector3(),
  stack: new THREE.Vector3(),
  tangent: new THREE.Vector3(),
  orbit: new THREE.Quaternion(),
  spin: new THREE.Quaternion(),
  stacked: new THREE.Quaternion(),
  euler: new THREE.Euler(),
};

type CoinSwirlProps = {
  /** 0 = coins orbit loosely, 1 = merged into one stack. */
  merge?: number;
  /** Continuously demo the merge (three emails → one transaction). */
  loop?: boolean;
};

/**
 * Anodised coins threaded on a tilted ring (faces along the ring, each spinning slowly on
 * the wire). The merge spirals them inward in a staggered cascade into one hand-stacked
 * column, then releases them — a seamless GSAP loop.
 */
export function CoinSwirlScene({ merge = 0, loop = false }: CoinSwirlProps) {
  const reduced = useReducedMotion() ?? false;
  const geometry = useCoinGeometry("lite");
  const materials = useMemo(() => TINTS.map((tint) => createAnodised(tint)), []);
  useOwnReflections(materials);
  useEffect(() => () => materials.forEach((material) => material.dispose()), [materials]);

  const layout = useMemo(() => {
    const random = createRandom(11);
    return Array.from({ length: COUNT }, (_, index) => ({
      angle: (index / COUNT) * TAU + randomBetween(random, -0.07, 0.07),
      radius: RING + randomBetween(random, -0.07, 0.07),
      lift: randomBetween(random, -0.05, 0.05),
      spin: randomBetween(random, 0, TAU),
      spinRate: randomBetween(random, 0.3, 0.6) * (random() < 0.5 ? -1 : 1),
      twist: randomBetween(random, 0, TAU),
      jitter: [randomBetween(random, -0.014, 0.014), randomBetween(random, -0.014, 0.014)] as const,
      order: index / (COUNT - 1),
      material: index % TINTS.length,
    }));
  }, []);

  const state = useRef({ merge });
  const coins = useRef<Array<THREE.Mesh | null>>([]);
  const group = useRef<THREE.Group>(null);

  useGSAP(
    () => {
      const target = state.current;
      if (!loop || reduced) {
        gsap.to(target, { merge, duration: reduced ? 0 : 1.2, ease: "power2.inOut" });
        return;
      }
      gsap
        .timeline({ repeat: -1, defaults: { ease: "none" } })
        .set(target, { merge: 0 })
        .to(target, { merge: 1, duration: 1.8 }, 3.4)
        .to(target, { merge: 0, duration: 1.6 }, 6.6);
    },
    { dependencies: [loop, merge, reduced] },
  );

  useFrame((frameState) => {
    const time = reduced ? 2.4 : frameState.clock.elapsedTime;
    const master = state.current.merge;
    if (group.current) group.current.rotation.y = Math.sin(time * 0.21) * 0.16;

    layout.forEach((coin, index) => {
      const mesh = coins.current[index];
      if (!mesh) return;
      const progress = easeMerge(Math.min(Math.max(master * (1 + STAGGER) - STAGGER * coin.order, 0), 1));
      const angle = coin.angle + time * ORBIT_SPEED;
      const radius = coin.radius * (1 - progress);

      // Orbit: a point on the tilted ring, shrinking into a spiral as the coin merges.
      scratch.position.set(Math.cos(angle) * radius, coin.lift * (1 - progress), Math.sin(angle) * radius).applyQuaternion(RING_TILT);
      scratch.tangent.set(-Math.sin(angle), 0, Math.cos(angle)).applyQuaternion(RING_TILT);
      scratch.orbit.setFromUnitVectors(FACE, scratch.tangent);
      scratch.spin.setFromAxisAngle(scratch.tangent, coin.spin + time * coin.spinRate);
      scratch.orbit.premultiply(scratch.spin);

      // Stack: face up, tilted toward the camera, hand-placed (twist + jitter), slowly turning.
      const height = (index - (COUNT - 1) / 2) * STACK_STEP;
      scratch.stack.copy(STACK_AXIS).multiplyScalar(height);
      scratch.stack.x += coin.jitter[0];
      scratch.stack.z += coin.jitter[1];
      scratch.stacked.setFromEuler(scratch.euler.set(-Math.PI / 2 + STACK_TILT, 0, coin.twist + time * 0.22));

      mesh.position.copy(scratch.position).multiplyScalar(1 - progress).addScaledVector(scratch.stack, progress);
      mesh.quaternion.slerpQuaternions(scratch.orbit, scratch.stacked, progress);
    });
  });

  return (
    <group ref={group}>
      {layout.map((coin, index) => {
        const material = materials[coin.material];
        return material ? (
          <mesh
            key={index}
            ref={(mesh) => {
              coins.current[index] = mesh;
            }}
            geometry={geometry}
            material={material}
            scale={SCALE}
          />
        ) : null;
      })}
    </group>
  );
}
