"use client";

import { Environment, Lightformer } from "@react-three/drei";
import { useEffect, useMemo } from "react";
import * as THREE from "three";

type GradientDomeProps = { zenith: string; horizon: string; ground: string; intensity?: number };

/** Inside-out sphere painting a sky gradient into the environment cube (HDR, linear). */
function GradientDome({ zenith, horizon, ground, intensity = 1 }: GradientDomeProps) {
  const material = useMemo(
    () =>
      new THREE.ShaderMaterial({
        side: THREE.BackSide,
        depthWrite: false,
        toneMapped: false,
        uniforms: {
          uZenith: { value: new THREE.Color(zenith).multiplyScalar(intensity) },
          uHorizon: { value: new THREE.Color(horizon).multiplyScalar(intensity) },
          uGround: { value: new THREE.Color(ground).multiplyScalar(intensity) },
        },
        vertexShader: /* glsl */ `
          varying vec3 vDirection;
          void main() {
            vDirection = normalize(position);
            gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
          }
        `,
        fragmentShader: /* glsl */ `
          uniform vec3 uZenith;
          uniform vec3 uHorizon;
          uniform vec3 uGround;
          varying vec3 vDirection;
          void main() {
            float h = normalize(vDirection).y;
            vec3 sky = mix(uHorizon, uZenith, pow(max(h, 0.0), 0.55));
            vec3 under = mix(uHorizon, uGround, pow(max(-h, 0.0), 0.4));
            gl_FragColor = vec4(h >= 0.0 ? sky : under, 1.0);
          }
        `,
      }),
    [zenith, horizon, ground, intensity],
  );
  useEffect(() => () => material.dispose(), [material]);
  return (
    <mesh material={material} scale={60}>
      <sphereGeometry args={[1, 48, 24]} />
    </mesh>
  );
}

/**
 * Product studio. "dark": a near-black cove so metals on light cards keep contrast in their
 * reflections. "light": an airy lavender cove for pastel dielectrics and glass. Both share
 * a large key softbox, two strip lights and violet / pink / blue gels that give anodised
 * coins and the chrome dome their colour shifts.
 */
export function ProductStudioEnvironment({ tone = "dark" }: { tone?: "dark" | "light" }) {
  const light = tone === "light";
  return (
    <Environment resolution={512} frames={1}>
      {light ? (
        // Pale ground and a lit floor card: down-tilted metal faces stay golden, not muddy.
        <GradientDome zenith="#ffffff" horizon="#e3dcf7" ground="#c4bbe3" intensity={0.9} />
      ) : (
        <GradientDome zenith="#2a2148" horizon="#0f0c1d" ground="#050409" />
      )}
      <Lightformer form="rect" color="#ffffff" intensity={3.4} position={[-3.5, 5.5, 4]} scale={[6, 5, 1]} />
      {/* Overhead box: up-facing chrome (the dome's face) rolls from bright lavender to dark. */}
      <Lightformer form="rect" color="#efe9ff" intensity={3.2} position={[-1, 7, -1.5]} scale={[8, 6, 1]} />
      <Lightformer form="rect" color="#f3efff" intensity={4.2} position={[6, 0.5, 1.5]} scale={[1.3, 9, 1]} />
      <Lightformer form="rect" color="#c2b0ff" intensity={2.4} position={[-6.5, 0, -1]} scale={[1, 8, 1]} />
      <Lightformer form="rect" color="#b49cff" intensity={2} position={[0, 3, -7]} scale={[9, 2.2, 1]} />
      <Lightformer form="ring" color="#ff6ad5" intensity={2.4} position={[-5, -2, -3]} scale={4.5} />
      <Lightformer form="rect" color="#5a8dff" intensity={1.1} position={[5, -3.5, -2.5]} scale={[3.5, 3, 1]} />
      <Lightformer
        form="rect"
        color={light ? "#f4efff" : "#6d4aff"}
        intensity={light ? 1.2 : 0.5}
        position={[0, -6, 0]}
        scale={[12, 12, 1]}
      />
    </Environment>
  );
}
