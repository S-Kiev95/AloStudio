/**
 * Pure physics helpers for the stretchable 3D rubber logos.
 *
 * All geometry coordinates live in normalized logo-local space where the logo
 * spans roughly [-1, +1] along X and Y (`logoSize = 2`). Keeping the math pure
 * lets vitest verify the Gaussian falloff, progressive stretch resistance,
 * non-folding deformation, and damped jelly-spring settling without WebGL.
 */

export interface Vec2 {
  x: number;
  y: number;
}

export interface Vec3 {
  x: number;
  y: number;
  z: number;
}

export interface ClampedPull {
  x: number;
  y: number;
  /** Resulting clamped displacement magnitude in local units. */
  magnitude: number;
  /** Fraction of the maximum stretch limit in [0, 1). */
  ratio: number;
}

export interface RubberPhysicsConfig {
  /** Maximum stretch distance as a multiple of `logoSize` (~1.5x). */
  maxStretchRatio: number;
  /** Gaussian falloff sigma as a fraction of `logoSize`. */
  falloffSigmaRatio: number;
  /** Minimum global follow when pulling outward so the far side moves little. */
  baseFollow: number;
  /** Raised global follow when pushing inward across the body to prevent folding. */
  inwardFollowMax: number;
  /** Per-vertex spring stiffness k (rad^2/s^2). */
  springStiffness: number;
  /** Per-vertex viscous damping c (1/s). */
  springDamping: number;
  /** Subtle stiffness reduction near the grabbed tip for wavy gelatin rebound. */
  tipSoftness: number;
  /** Whole-logo squash spring stiffness. */
  squashStiffness: number;
  /** Whole-logo squash spring damping. */
  squashDamping: number;
  /** Initial squash velocity injected per unit stretch ratio on release. */
  squashKick: number;
  /** Maximum absolute squash factor on the whole logo. */
  squashMax: number;
  /** Settling threshold for displacement (local units). */
  restPosEps: number;
  /** Settling threshold for velocity (local units / s). */
  restVelEps: number;
  /** Maximum substep duration (seconds) for unconditional numerical stability. */
  maxSubstepDt: number;
}

export const RUBBER_DEFAULTS: RubberPhysicsConfig = {
  maxStretchRatio: 1.5,
  falloffSigmaRatio: 0.38,
  baseFollow: 0.08,
  inwardFollowMax: 0.44,
  springStiffness: 260,
  springDamping: 10.6,
  tipSoftness: 0.14,
  squashStiffness: 220,
  squashDamping: 10.5,
  squashKick: 1.9,
  squashMax: 0.14,
  restPosEps: 0.004,
  restVelEps: 0.025,
  maxSubstepDt: 1 / 120,
};

export interface SquashState {
  /** Squash amount along `axis` (positive compresses along axis, expands across). */
  s: number;
  /** Rate of change of `s` (1/s). */
  sv: number;
  /** Pull axis angle in local XY radians. */
  axis: number;
}

export interface SpringStepResult {
  /** True while any vertex is still moving above rest tolerance. */
  active: boolean;
  maxDisp: number;
  maxVel: number;
}

/**
 * Progressive rubber resistance: 1:1 for gentle pulls, then smoothly saturating
 * via `tanh` so displacement never reaches or exceeds `maxStretch`.
 */
export function softClampPull(
  dx: number,
  dy: number,
  maxStretch: number,
): ClampedPull {
  if (maxStretch <= 0) {
    return { x: 0, y: 0, magnitude: 0, ratio: 0 };
  }
  const raw = Math.hypot(dx, dy);
  if (raw < 1e-8) {
    return { x: 0, y: 0, magnitude: 0, ratio: 0 };
  }
  const ratio = Math.tanh(raw / maxStretch);
  const magnitude = maxStretch * ratio;
  const scale = magnitude / raw;
  return {
    x: dx * scale,
    y: dy * scale,
    magnitude,
    ratio,
  };
}

/**
 * Smooth Gaussian influence falloff in `[baseFollow, 1]` as a function of
 * squared distance from the grabbed point.
 */
export function gaussianFalloff(
  distSq: number,
  sigma: number,
  baseFollow = RUBBER_DEFAULTS.baseFollow,
): number {
  const b = Math.max(0, Math.min(1, baseFollow));
  if (sigma <= 0) return distSq <= 0 ? 1 : b;
  const g = Math.exp(-Math.max(0, distSq) / (2 * sigma * sigma));
  return b + (1 - b) * g;
}

/**
 * Compute per-vertex Gaussian pull weights, raising the floor smoothly if the
 * user pushes inward across the logo body so vertices never overtake each other.
 */
export function computePullWeights(
  restPositions: Float32Array,
  grabPoint: Vec3,
  pull: Vec2,
  logoSize: number,
  weightsOut?: Float32Array,
  config: RubberPhysicsConfig = RUBBER_DEFAULTS,
): Float32Array {
  const count = Math.floor(restPositions.length / 3);
  const out =
    weightsOut && weightsOut.length >= count
      ? weightsOut
      : new Float32Array(count);

  const half = Math.max(logoSize * 0.5, 1e-4);
  const pullMag = Math.hypot(pull.x, pull.y);
  let inwardFactor = 0;
  if (pullMag > 1e-6) {
    const grabMag = Math.hypot(grabPoint.x, grabPoint.y);
    if (grabMag > 1e-4) {
      // Negative dot means pulling a point on the perimeter back through the center.
      const alignment =
        (grabPoint.x * pull.x + grabPoint.y * pull.y) / (grabMag * pullMag);
      if (alignment < 0) {
        inwardFactor = Math.min(1, -alignment * Math.min(1, grabMag / half));
      }
    }
  }

  const baseFollow =
    config.baseFollow +
    (config.inwardFollowMax - config.baseFollow) * inwardFactor;
  // Slightly wider kernel when pushing inward keeps the Jacobian strictly positive.
  const sigma =
    Math.max(logoSize, 1e-4) *
    config.falloffSigmaRatio *
    (1 + 0.35 * inwardFactor);

  const gx = grabPoint.x;
  const gy = grabPoint.y;
  const gz = grabPoint.z;

  for (let i = 0; i < count; i++) {
    const i3 = i * 3;
    const dx = restPositions[i3]! - gx;
    const dy = restPositions[i3 + 1]! - gy;
    // Weight XY distance primarily, with a small Z contribution so raised marks
    // stay glued to the body face directly underneath them.
    const dz = (restPositions[i3 + 2]! - gz) * 0.35;
    out[i] = gaussianFalloff(dx * dx + dy * dy + dz * dz, sigma, baseFollow);
  }

  return out;
}

/**
 * Compute target per-vertex rubber displacements `(ux, uy, uz)` for a drag.
 *
 * Combines:
 *  - Soft-clamped Gaussian pull along the drag vector (bounded to ~1.5x logo size)
 *  - Subtle volume-preserving waist necking perpendicular to the pull
 *  - Gentle Z thinning + slight forward lift at the grabbed tip
 *  - Order-preserving guard when pushing inward across the body
 */
export function computeStretchedTargets(
  restPositions: Float32Array,
  grabPoint: Vec3,
  rawPull: Vec2,
  logoSize: number,
  targetsOut: Float32Array,
  weightsOut?: Float32Array,
  config: RubberPhysicsConfig = RUBBER_DEFAULTS,
): { clampedPull: ClampedPull; weights: Float32Array } {
  const maxStretch = Math.max(logoSize, 1e-4) * config.maxStretchRatio;
  const half = Math.max(logoSize * 0.5, 1e-4);

  // When pushing a perimeter point back across the logo center, add extra
  // resistance so the grabbed region glides smoothly without folding over.
  const rawMag = Math.hypot(rawPull.x, rawPull.y);
  const grabMag = Math.hypot(grabPoint.x, grabPoint.y);
  let inward = 0;
  if (rawMag > 1e-6 && grabMag > 1e-4) {
    const align =
      (grabPoint.x * rawPull.x + grabPoint.y * rawPull.y) / (grabMag * rawMag);
    if (align < 0) {
      inward = Math.min(1, -align * Math.min(1, grabMag / half));
    }
  }
  const effectiveMax = maxStretch * (1 - 0.38 * inward);
  const clampedPull = softClampPull(rawPull.x, rawPull.y, effectiveMax);

  const weights = computePullWeights(
    restPositions,
    grabPoint,
    clampedPull,
    logoSize,
    weightsOut,
    config,
  );

  const count = Math.floor(restPositions.length / 3);
  const mag = clampedPull.magnitude;
  if (mag < 1e-8) {
    targetsOut.fill(0, 0, count * 3);
    return { clampedPull, weights };
  }

  const dirX = clampedPull.x / mag;
  const dirY = clampedPull.y / mag;
  const perpX = -dirY;
  const perpY = dirX;
  const ratio = clampedPull.ratio;
  const gx = grabPoint.x;
  const gy = grabPoint.y;

  // Necking peaks at intermediate weights (w*(1-w)) where rubber stretches thin.
  const neckStrength = 0.14 * ratio * (1 - 0.6 * inward);
  const zThinStrength = 0.16 * ratio;
  const tipLift = 0.06 * logoSize * ratio;

  for (let i = 0; i < count; i++) {
    const i3 = i * 3;
    const rx = restPositions[i3]!;
    const ry = restPositions[i3 + 1]!;
    const rz = restPositions[i3 + 2]!;
    const w = weights[i]!;

    // Lateral distance from the pull ray passing through the grab point.
    const relX = rx - gx;
    const relY = ry - gy;
    const perpDist = relX * perpX + relY * perpY;
    const neck = -perpDist * neckStrength * 4 * w * (1 - w);

    targetsOut[i3] = clampedPull.x * w + perpX * neck;
    targetsOut[i3 + 1] = clampedPull.y * w + perpY * neck;
    // Slight thinning around z=0 plus gentle lift toward the camera at the tip.
    targetsOut[i3 + 2] = -rz * zThinStrength * w + tipLift * w * w;
  }

  return { clampedPull, weights };
}

/**
 * Integrate one 1D damped harmonic oscillator `x'' + c x' + k x = 0` over `dt`
 * using semi-implicit Euler with automatic substepping for stability.
 */
export function stepSpring1D(
  x: number,
  v: number,
  dt: number,
  stiffness = RUBBER_DEFAULTS.springStiffness,
  damping = RUBBER_DEFAULTS.springDamping,
  maxSubstepDt = RUBBER_DEFAULTS.maxSubstepDt,
): { x: number; v: number } {
  const clampedDt = Math.min(Math.max(dt, 0), 0.05);
  if (clampedDt <= 0) return { x, v };
  const steps = Math.max(1, Math.ceil(clampedDt / maxSubstepDt));
  const h = clampedDt / steps;
  let pos = x;
  let vel = v;
  for (let s = 0; s < steps; s++) {
    const acc = -stiffness * pos - damping * vel;
    vel += acc * h;
    pos += vel * h;
  }
  return { x: pos, v: vel };
}

/**
 * Step all per-vertex gelatin springs back toward zero displacement.
 *
 * Uses slightly lower stiffness near the grabbed tip (`tipSoftness`) so the
 * stretched zone whips back with an organic gelatin wave. Snaps cleanly to
 * exact zero once below rest thresholds so the WebGL loop can stop completely.
 */
export function stepVertexSprings(
  displacements: Float32Array,
  velocities: Float32Array,
  weights: Float32Array,
  dt: number,
  config: RubberPhysicsConfig = RUBBER_DEFAULTS,
): SpringStepResult {
  const clampedDt = Math.min(Math.max(dt, 0), 0.05);
  const count = Math.min(
    Math.floor(displacements.length / 3),
    Math.floor(velocities.length / 3),
    weights.length,
  );
  if (count === 0) {
    return { active: false, maxDisp: 0, maxVel: 0 };
  }

  const steps =
    clampedDt > 0 ? Math.max(1, Math.ceil(clampedDt / config.maxSubstepDt)) : 0;
  const h = steps > 0 ? clampedDt / steps : 0;
  const baseK = config.springStiffness;
  const c = config.springDamping;
  const softness = config.tipSoftness;

  let maxDisp = 0;
  let maxVel = 0;

  for (let i = 0; i < count; i++) {
    const i3 = i * 3;
    const k = baseK * (1 - softness * weights[i]!);

    let dx = displacements[i3]!;
    let dy = displacements[i3 + 1]!;
    let dz = displacements[i3 + 2]!;
    let vx = velocities[i3]!;
    let vy = velocities[i3 + 1]!;
    let vz = velocities[i3 + 2]!;

    for (let s = 0; s < steps; s++) {
      vx += (-k * dx - c * vx) * h;
      dx += vx * h;
      vy += (-k * dy - c * vy) * h;
      dy += vy * h;
      vz += (-k * dz - c * vz) * h;
      dz += vz * h;
    }

    displacements[i3] = dx;
    displacements[i3 + 1] = dy;
    displacements[i3 + 2] = dz;
    velocities[i3] = vx;
    velocities[i3 + 1] = vy;
    velocities[i3 + 2] = vz;

    const absDisp = Math.max(Math.abs(dx), Math.abs(dy), Math.abs(dz));
    const absVel = Math.max(Math.abs(vx), Math.abs(vy), Math.abs(vz));
    if (absDisp > maxDisp) maxDisp = absDisp;
    if (absVel > maxVel) maxVel = absVel;
  }

  if (maxDisp < config.restPosEps && maxVel < config.restVelEps) {
    displacements.fill(0, 0, count * 3);
    velocities.fill(0, 0, count * 3);
    return { active: false, maxDisp: 0, maxVel: 0 };
  }

  return { active: true, maxDisp, maxVel };
}

/**
 * Create a whole-logo squash impulse along the release pull direction.
 */
export function createSquashKick(
  pullX: number,
  pullY: number,
  logoSize: number,
  config: RubberPhysicsConfig = RUBBER_DEFAULTS,
): SquashState {
  const maxStretch = Math.max(logoSize, 1e-4) * config.maxStretchRatio;
  const mag = Math.hypot(pullX, pullY);
  if (mag < 1e-5) {
    return { s: 0, sv: 0, axis: 0 };
  }
  const intensity = Math.min(1, mag / maxStretch);
  return {
    s: 0,
    sv: intensity * config.squashKick,
    axis: Math.atan2(pullY, pullX),
  };
}

/**
 * Advance the whole-logo squash-and-stretch spring in place.
 * Returns `true` while still wobbling, `false` once snapped cleanly to rest.
 */
export function stepSquashSpring(
  state: SquashState,
  dt: number,
  config: RubberPhysicsConfig = RUBBER_DEFAULTS,
): boolean {
  const next = stepSpring1D(
    state.s,
    state.sv,
    dt,
    config.squashStiffness,
    config.squashDamping,
    config.maxSubstepDt,
  );
  state.s = Math.max(-config.squashMax, Math.min(config.squashMax, next.x));
  state.sv = next.v;

  if (Math.abs(state.s) < 0.002 && Math.abs(state.sv) < 0.015) {
    state.s = 0;
    state.sv = 0;
    return false;
  }
  return true;
}
