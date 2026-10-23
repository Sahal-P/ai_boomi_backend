import * as THREE from "three";

export type Vec3 = readonly [number, number, number];

export type TrackOptions = {
  /** Centreline control points (centripetal Catmull-Rom). */
  points: readonly Vec3[];
  /** Channel outer radius: the centreline sits this far above whatever the channel rests on. */
  outerRadius: number;
  wall: number;
  coinRadius: number;
  /** Slow-motion gravity (units/s²) and rolling drag (units/s² along the path). */
  gravity: number;
  drag: number;
  entrySpeed: number;
  minSpeed: number;
  /** Share of the coin's lean the channel banks by; the rest is the coin riding up the wall. */
  bank: number;
};

export type CoinPose = { position: THREE.Vector3; quaternion: THREE.Quaternion };

export type Track = {
  length: number;
  /** Seconds a coin takes from entry to exit. */
  duration: number;
  /** Writes the coin pose `seconds` after entry; false once it is off the track. */
  poseAt(seconds: number, pose: CoinPose): boolean;
  createGeometry(segments: number, arcSteps: number): THREE.BufferGeometry;
};

const SAMPLES = 1600;
const UP = new THREE.Vector3(0, 1, 0);
const Z_AXIS = new THREE.Vector3(0, 0, 1);
const MAX_LEAN = 0.6;

/** Three box-filter passes (≈ Gaussian) along the path, clamped at the ends. */
function smooth(values: Float32Array, radius: number): void {
  if (radius < 1) return;
  const source = new Float32Array(values.length);
  const last = values.length - 1;
  for (let pass = 0; pass < 3; pass += 1) {
    source.set(values);
    let sum = 0;
    for (let k = -radius; k <= radius; k += 1) sum += source[Math.min(Math.max(k, 0), last)] ?? 0;
    for (let index = 0; index <= last; index += 1) {
      values[index] = sum / (radius * 2 + 1);
      sum += (source[Math.min(index + radius + 1, last)] ?? 0) - (source[Math.max(index - radius, 0)] ?? 0);
    }
  }
}

type ProfilePoint = { x: number; y: number; nx: number; ny: number };

/**
 * Half-pipe cross-section in (side, up): an outer arc under the centre, rounded lips that
 * rise slightly above it, and the inner arc the coin rolls in. Closed and smooth.
 */
function channelProfile(outer: number, inner: number, arcSteps: number, capSteps = 8): ProfilePoint[] {
  const lift = 0.16;
  const from = Math.PI - lift;
  const to = 2 * Math.PI + lift;
  const middle = (outer + inner) / 2;
  const lip = (outer - inner) / 2;
  const points: ProfilePoint[] = [];
  const arc = (radius: number, start: number, end: number, sign: number) => {
    for (let k = 0; k <= arcSteps; k += 1) {
      const angle = start + ((end - start) * k) / arcSteps;
      const cos = Math.cos(angle);
      const sin = Math.sin(angle);
      points.push({ x: radius * cos, y: radius * sin, nx: sign * cos, ny: sign * sin });
    }
  };
  const cap = (angle: number, direction: number) => {
    const radial = [Math.cos(angle), Math.sin(angle)] as const;
    const tangent = [-Math.sin(angle) * direction, Math.cos(angle) * direction] as const;
    const centre = [middle * radial[0], middle * radial[1]] as const;
    for (let k = 1; k < capSteps; k += 1) {
      const turn = (Math.PI * k) / capSteps;
      // Outer lip side → over the end → inner side (direction picks which way "over" is).
      const flip = direction > 0 ? 1 : -1;
      const nx = flip * (Math.cos(turn) * radial[0]) + Math.sin(turn) * tangent[0];
      const ny = flip * (Math.cos(turn) * radial[1]) + Math.sin(turn) * tangent[1];
      points.push({ x: centre[0] + lip * nx, y: centre[1] + lip * ny, nx, ny });
    }
  };
  arc(outer, from, to, 1);
  cap(to, 1);
  arc(inner, to, from, -1);
  cap(from, -1);
  return points;
}

export function createTrack(options: TrackOptions): Track {
  const { outerRadius, wall, coinRadius, gravity, drag, entrySpeed, minSpeed, bank } = options;
  const curve = new THREE.CatmullRomCurve3(
    options.points.map(([x, y, z]) => new THREE.Vector3(x, y, z)),
    false,
    "centripetal",
    0.5,
  );
  const length = curve.getLength();
  const step = length / (SAMPLES - 1);
  const rest = outerRadius - wall - coinRadius;

  const centre = new Float32Array(SAMPLES * 3);
  const tangent = new Float32Array(SAMPLES * 3);
  const up = new Float32Array(SAMPLES * 3);
  const side = new Float32Array(SAMPLES * 3);
  const point = new THREE.Vector3();
  const along = new THREE.Vector3();
  const normal = new THREE.Vector3();
  const lateral = new THREE.Vector3();
  for (let index = 0; index < SAMPLES; index += 1) {
    const at = index / (SAMPLES - 1);
    curve.getPointAt(at, point).toArray(centre, index * 3);
    curve.getTangentAt(at, along).normalize().toArray(tangent, index * 3);
    normal.copy(UP).addScaledVector(along, -along.y).normalize().toArray(up, index * 3);
    lateral.crossVectors(along, normal).normalize().toArray(side, index * 3);
  }

  // Signed lateral curvature: > 0 when the path turns toward +side.
  const curvature = new Float32Array(SAMPLES);
  for (let index = 0; index < SAMPLES; index += 1) {
    const previous = Math.max(index - 1, 0);
    const next = Math.min(index + 1, SAMPLES - 1);
    along.fromArray(tangent, next * 3).sub(point.fromArray(tangent, previous * 3));
    curvature[index] = along.dot(lateral.fromArray(side, index * 3)) / ((next - previous) * step);
  }
  smooth(curvature, Math.round(0.3 / step));

  // Energy along the path: drops speed the coin up, drag and climbs slow it down.
  const speed = new Float32Array(SAMPLES);
  const time = new Float32Array(SAMPLES);
  speed[0] = entrySpeed;
  for (let index = 1; index < SAMPLES; index += 1) {
    const drop = (centre[(index - 1) * 3 + 1] ?? 0) - (centre[index * 3 + 1] ?? 0);
    const previous = speed[index - 1] ?? minSpeed;
    const current = Math.sqrt(Math.max(previous * previous + 2 * gravity * drop - 2 * drag * step, minSpeed * minSpeed));
    speed[index] = current;
    time[index] = (time[index - 1] ?? 0) + (2 * step) / (previous + current);
  }
  const duration = time[SAMPLES - 1] ?? 0;

  // Lean into turns from the effective gravity v²κ/g (eased so it stays elegant).
  const lean = new Float32Array(SAMPLES);
  for (let index = 0; index < SAMPLES; index += 1) {
    const v = speed[index] ?? 0;
    const angle = Math.atan((v * v * (curvature[index] ?? 0)) / gravity) * 0.55;
    lean[index] = Math.min(Math.max(angle, -MAX_LEAN), MAX_LEAN);
  }
  smooth(lean, Math.round(0.45 / step));

  // Interpolated frame at a fractional sample index.
  const frame = {
    centre: new THREE.Vector3(),
    tangent: new THREE.Vector3(),
    up: new THREE.Vector3(),
    side: new THREE.Vector3(),
    lean: 0,
  };
  const scratch = new THREE.Vector3();
  const sampleFrame = (position: number) => {
    const clamped = Math.min(Math.max(position, 0), SAMPLES - 1);
    const lo = Math.min(Math.floor(clamped), SAMPLES - 2);
    const f = clamped - lo;
    const blend = (array: Float32Array, target: THREE.Vector3) =>
      target.fromArray(array, lo * 3).lerp(scratch.fromArray(array, (lo + 1) * 3), f);
    blend(centre, frame.centre);
    blend(tangent, frame.tangent).normalize();
    blend(up, frame.up);
    frame.up.addScaledVector(frame.tangent, -frame.up.dot(frame.tangent)).normalize();
    frame.side.crossVectors(frame.tangent, frame.up);
    frame.lean = (lean[lo] ?? 0) * (1 - f) + (lean[lo + 1] ?? 0) * f;
    return frame;
  };

  const coinUp = new THREE.Vector3();
  const coinFace = new THREE.Vector3();
  const basis = new THREE.Matrix4();
  const roll = new THREE.Quaternion();

  return {
    length,
    duration,
    poseAt(seconds, pose) {
      if (seconds < 0 || seconds > duration) return false;
      let lo = 0;
      let hi = SAMPLES - 1;
      while (hi - lo > 1) {
        const mid = (lo + hi) >> 1;
        if ((time[mid] ?? 0) <= seconds) lo = mid;
        else hi = mid;
      }
      const t0 = time[lo] ?? 0;
      const t1 = time[hi] ?? 0;
      const position = lo + (t1 > t0 ? (seconds - t0) / (t1 - t0) : 0);
      const { centre: c, tangent: t, up: u, side: s, lean: angle } = sampleFrame(position);
      coinUp.copy(u).multiplyScalar(Math.cos(angle)).addScaledVector(s, Math.sin(angle));
      pose.position.copy(c).addScaledVector(coinUp, -rest);
      coinFace.crossVectors(t, coinUp);
      basis.makeBasis(t, coinUp, coinFace);
      pose.quaternion.setFromRotationMatrix(basis);
      pose.quaternion.multiply(roll.setFromAxisAngle(Z_AXIS, -(position * step) / coinRadius));
      return true;
    },
    createGeometry(segments, arcSteps) {
      const profile = channelProfile(outerRadius, outerRadius - wall, arcSteps);
      const ring = profile.length;
      const positions = new Float32Array((segments + 1) * ring * 3);
      const normals = new Float32Array((segments + 1) * ring * 3);
      const bankUp = new THREE.Vector3();
      const bankSide = new THREE.Vector3();
      for (let i = 0; i <= segments; i += 1) {
        const { centre: c, up: u, side: s, lean: angle } = sampleFrame(((SAMPLES - 1) * i) / segments);
        const tilt = angle * bank;
        bankUp.copy(u).multiplyScalar(Math.cos(tilt)).addScaledVector(s, Math.sin(tilt));
        bankSide.copy(s).multiplyScalar(Math.cos(tilt)).addScaledVector(u, -Math.sin(tilt));
        profile.forEach(({ x, y, nx, ny }, j) => {
          const offset = (i * ring + j) * 3;
          scratch.copy(c).addScaledVector(bankSide, x).addScaledVector(bankUp, y).toArray(positions, offset);
          scratch.copy(bankSide).multiplyScalar(nx).addScaledVector(bankUp, ny).toArray(normals, offset);
        });
      }
      const indices: number[] = [];
      for (let i = 0; i < segments; i += 1) {
        for (let j = 0; j < ring; j += 1) {
          const a = i * ring + j;
          const b = i * ring + ((j + 1) % ring);
          const c = (i + 1) * ring + ((j + 1) % ring);
          const d = (i + 1) * ring + j;
          indices.push(a, d, b, b, d, c);
        }
      }
      const geometry = new THREE.BufferGeometry();
      geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
      geometry.setAttribute("normal", new THREE.BufferAttribute(normals, 3));
      geometry.setIndex(indices);
      geometry.computeBoundingSphere();
      return geometry;
    },
  };
}
