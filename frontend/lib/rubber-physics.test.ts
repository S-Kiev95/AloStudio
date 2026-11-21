import { describe, expect, it } from "vitest";

import {
  computePullWeights,
  computeStretchedTargets,
  createSquashKick,
  gaussianFalloff,
  RUBBER_DEFAULTS,
  softClampPull,
  stepSpring1D,
  stepSquashSpring,
  stepVertexSprings,
} from "./rubber-physics";

describe("softClampPull", () => {
  it("returns zero for zero input or non-positive maxStretch", () => {
    expect(softClampPull(0, 0, 3)).toEqual({
      x: 0,
      y: 0,
      magnitude: 0,
      ratio: 0,
    });
    expect(softClampPull(2, 1, 0)).toEqual({
      x: 0,
      y: 0,
      magnitude: 0,
      ratio: 0,
    });
  });

  it("tracks small pulls nearly 1:1 and preserves direction", () => {
    const res = softClampPull(0.06, 0.08, 3.0); // raw = 0.1
    expect(res.magnitude).toBeCloseTo(0.1, 3);
    expect(res.x / res.magnitude).toBeCloseTo(0.6, 5);
    expect(res.y / res.magnitude).toBeCloseTo(0.8, 5);
  });

  it("increases resistance monotonically and never exceeds maxStretch", () => {
    const maxStretch = 3.0;
    const samples = [0.2, 0.8, 1.5, 3.0, 6.0, 20.0, 500.0].map((d) =>
      softClampPull(d, 0, maxStretch),
    );

    for (let i = 1; i < samples.length; i++) {
      expect(samples[i]!.magnitude).toBeGreaterThanOrEqual(
        samples[i - 1]!.magnitude,
      );
    }
    for (const s of samples) {
      expect(s.magnitude).toBeLessThanOrEqual(maxStretch);
      expect(s.ratio).toBeGreaterThanOrEqual(0);
      expect(s.ratio).toBeLessThanOrEqual(1);
    }
    // Progressive resistance: pulling twice as far yields less than twice the stretch.
    const a = softClampPull(1.5, 0, maxStretch).magnitude;
    const b = softClampPull(3.0, 0, maxStretch).magnitude;
    expect(b - a).toBeLessThan(a);
  });
});

describe("gaussianFalloff", () => {
  it("equals 1 at distance zero and decreases smoothly toward baseFollow", () => {
    const sigma = 0.76;
    const base = 0.08;
    const w0 = gaussianFalloff(0, sigma, base);
    const w1 = gaussianFalloff(0.25, sigma, base);
    const w2 = gaussianFalloff(1.0, sigma, base);
    const wFar = gaussianFalloff(100, sigma, base);

    expect(w0).toBe(1);
    expect(w1).toBeLessThan(w0);
    expect(w2).toBeLessThan(w1);
    expect(wFar).toBeCloseTo(base, 6);
    expect(wFar).toBeGreaterThanOrEqual(base);
  });
});

describe("computeStretchedTargets", () => {
  function makeGridMesh(n = 11): Float32Array {
    const out = new Float32Array(n * n * 3);
    let idx = 0;
    for (let iy = 0; iy < n; iy++) {
      const y = -1 + (2 * iy) / (n - 1);
      for (let ix = 0; ix < n; ix++) {
        const x = -1 + (2 * ix) / (n - 1);
        out[idx++] = x;
        out[idx++] = y;
        out[idx++] = 0.25;
      }
    }
    return out;
  }

  it("moves the grabbed point with the clamped pull while the far side follows little", () => {
    const rest = makeGridMesh(11); // logoSize = 2
    const targets = new Float32Array(rest.length);
    const grab = { x: 1, y: 0, z: 0.25 };
    const { clampedPull, weights } = computeStretchedTargets(
      rest,
      grab,
      { x: 2.0, y: 0 },
      2.0,
      targets,
    );

    // Middle row (iy = 5): ix = 0 is (-1, 0), ix = 10 is (+1, 0).
    const farIdx = 5 * 11 + 0;
    const nearIdx = 5 * 11 + 10;

    expect(weights[nearIdx]).toBeCloseTo(1, 5);
    expect(weights[farIdx]!).toBeLessThan(0.2);
    expect(targets[nearIdx * 3]).toBeCloseTo(clampedPull.x, 4);
    expect(targets[farIdx * 3]!).toBeLessThan(clampedPull.x * 0.2);
  });

  it("never exceeds ~1.5x logo size even under extreme drag", () => {
    const rest = makeGridMesh(9);
    const targets = new Float32Array(rest.length);
    const logoSize = 2.0;
    const maxAllowed = logoSize * RUBBER_DEFAULTS.maxStretchRatio;

    computeStretchedTargets(
      rest,
      { x: 0.5, y: 0.5, z: 0.25 },
      { x: 200, y: 150 },
      logoSize,
      targets,
    );

    for (let i = 0; i < rest.length; i += 3) {
      const xyDisp = Math.hypot(targets[i]!, targets[i + 1]!);
      expect(xyDisp).toBeLessThanOrEqual(maxAllowed + 1e-4);
    }
  });

  it("preserves monotonic vertex ordering without folding on both outward and inward drags", () => {
    const n = 15;
    const rest = makeGridMesh(n);
    const targets = new Float32Array(rest.length);
    const midRow = Math.floor(n / 2);

    // Outward pull from right edge (+1, 0) to the right (+10, 0).
    computeStretchedTargets(
      rest,
      { x: 1, y: 0, z: 0.25 },
      { x: 10, y: 0 },
      2.0,
      targets,
    );
    for (let ix = 1; ix < n; ix++) {
      const prev = midRow * n + (ix - 1);
      const curr = midRow * n + ix;
      const xPrev = rest[prev * 3]! + targets[prev * 3]!;
      const xCurr = rest[curr * 3]! + targets[curr * 3]!;
      expect(xCurr).toBeGreaterThan(xPrev);
    }

    // Inward push from left edge (-1, 0) pushed hard across the center (+10, 0).
    computeStretchedTargets(
      rest,
      { x: -1, y: 0, z: 0.25 },
      { x: 10, y: 0 },
      2.0,
      targets,
    );
    for (let ix = 1; ix < n; ix++) {
      const prev = midRow * n + (ix - 1);
      const curr = midRow * n + ix;
      const xPrev = rest[prev * 3]! + targets[prev * 3]!;
      const xCurr = rest[curr * 3]! + targets[curr * 3]!;
      expect(xCurr).toBeGreaterThan(xPrev);
    }
  });

  it("raises base follow when pushing inward compared to pulling outward", () => {
    const rest = new Float32Array([-1, 0, 0, 1, 0, 0]);
    const outward = computePullWeights(
      rest,
      { x: 1, y: 0, z: 0 },
      { x: 1, y: 0 },
      2.0,
    );
    const inward = computePullWeights(
      rest,
      { x: 1, y: 0, z: 0 },
      { x: -1, y: 0 },
      2.0,
    );
    expect(inward[0]!).toBeGreaterThan(outward[0]!);
  });
});

describe("damped jelly springs", () => {
  it("oscillates 2–4 visible times and settles in ~0.8–1.2 s", () => {
    let x = 2.0;
    let v = 0;
    const dt = 1 / 60;
    let visibleCrossings = 0;
    let prevSign = Math.sign(x);
    let settledAt = -1;

    for (let frame = 1; frame <= 180; frame++) {
      const next = stepSpring1D(x, v, dt);
      x = next.x;
      v = next.v;
      const sign = Math.sign(x);
      if (sign !== 0 && sign !== prevSign) {
        if (Math.abs(v) > 0.35) {
          visibleCrossings += 1;
        }
        prevSign = sign;
      }
      if (
        settledAt < 0 &&
        Math.abs(x) < RUBBER_DEFAULTS.restPosEps &&
        Math.abs(v) < RUBBER_DEFAULTS.restVelEps
      ) {
        settledAt = frame * dt;
      }
    }

    expect(visibleCrossings).toBeGreaterThanOrEqual(2);
    expect(visibleCrossings).toBeLessThanOrEqual(4);
    expect(settledAt).toBeGreaterThanOrEqual(0.8);
    expect(settledAt).toBeLessThanOrEqual(1.25);
  });

  it("steps per-vertex springs cleanly to exact zero and survives dt spikes", () => {
    const disp = new Float32Array([1.8, -0.9, 0.1, 0.2, -0.1, 0.0]);
    const vel = new Float32Array(6);
    const weights = new Float32Array([1.0, 0.1]);

    // Huge dt spike (e.g. background tab) should stay finite and bounded.
    const spike = stepVertexSprings(disp, vel, weights, 0.5);
    expect(spike.active).toBe(true);
    expect(Number.isFinite(disp[0])).toBe(true);
    expect(Math.abs(disp[0]!)).toBeLessThan(3);

    // Run until settled (~1.0–1.3 s at 60 fps).
    let active = true;
    let elapsed = 0;
    while (active && elapsed < 2.5) {
      elapsed += 1 / 60;
      active = stepVertexSprings(disp, vel, weights, 1 / 60).active;
    }

    expect(active).toBe(false);
    expect(elapsed).toBeGreaterThanOrEqual(0.75);
    expect(elapsed).toBeLessThanOrEqual(1.4);
    expect(Array.from(disp)).toEqual([0, 0, 0, 0, 0, 0]);
    expect(Array.from(vel)).toEqual([0, 0, 0, 0, 0, 0]);
  });

  it("creates and settles a bounded whole-logo squash wobble on release", () => {
    const squash = createSquashKick(2.0, 1.0, 2.0);
    expect(squash.sv).toBeGreaterThan(0);
    expect(squash.axis).toBeCloseTo(Math.atan2(1, 2), 5);

    let peak = 0;
    let active = true;
    let elapsed = 0;
    while (active && elapsed < 2.5) {
      elapsed += 1 / 60;
      active = stepSquashSpring(squash, 1 / 60);
      peak = Math.max(peak, Math.abs(squash.s));
    }

    expect(peak).toBeGreaterThan(0.02);
    expect(peak).toBeLessThanOrEqual(RUBBER_DEFAULTS.squashMax);
    expect(active).toBe(false);
    expect(squash.s).toBe(0);
    expect(squash.sv).toBe(0);
  });
});
