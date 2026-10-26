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
 * Product studio in the glass palette. "dark": an ink cove so metals on light cards keep
 * contrast in their reflections. "light": a cove in the field's grey for pale dielectrics and
 * glass. Both share a large key softbox and two strip lights, and the field's glows as gels —
 * cool from the left and below, warm from the right — so metals and glass catch the same light
 * as the page around them.
 */
export function ProductStudioEnvironment({ tone = "dark" }: { tone?: "dark" | "light" }) {
  const light = tone === "light";
  return (
    <Environment resolution={512} frames={1}>
      {light ? (
        // Pale ground and a lit floor card: down-tilted metal faces stay golden, not muddy.
        <GradientDome zenith="#ffffff" horizon="#e4e6e9" ground="#c5cad0" intensity={0.9} />
      ) : (
        <GradientDome zenith="#2a2e35" horizon="#0e1013" ground="#050506" />
      )}
      <Lightformer form="rect" color="#ffffff" intensity={3.4} position={[-3.5, 5.5, 4]} scale={[6, 5, 1]} />
      {/* Overhead box: up-facing faces (the dome's face) roll from bright to dark. */}
      <Lightformer form="rect" color="#f2f5f7" intensity={3.2} position={[-1, 7, -1.5]} scale={[8, 6, 1]} />
      <Lightformer form="rect" color="#f7f8fa" intensity={4.2} position={[6, 0.5, 1.5]} scale={[1.3, 9, 1]} />
      <Lightformer form="rect" color="#b9deeb" intensity={2.4} position={[-6.5, 0, -1]} scale={[1, 8, 1]} />
      <Lightformer form="rect" color="#e8d3b0" intensity={2} position={[0, 3, -7]} scale={[9, 2.2, 1]} />
      <Lightformer form="ring" color="#b9deeb" intensity={2.4} position={[-5, -2, -3]} scale={4.5} />
      <Lightformer form="rect" color="#f2c879" intensity={1.4} position={[5, -3.5, -2.5]} scale={[3.5, 3, 1]} />
      <Lightformer
        form="rect"
        color={light ? "#f3f4f6" : "#62666d"}
        intensity={light ? 1.2 : 0.5}
        position={[0, -6, 0]}
        scale={[12, 12, 1]}
      />
    </Environment>
  );
}
