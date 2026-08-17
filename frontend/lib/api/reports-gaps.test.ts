import { describe, expect, it } from "vitest";

import { fillDailyGaps } from "./reports";

const DAY = 86_400;
// A UTC midnight, so the arithmetic below is readable at offset 0.
const D10 = Date.UTC(2026, 7, 10) / 1000;

const range = { since: D10 + 3600, until: D10 + 6 * DAY + 3600 };

describe("fillDailyGaps", () => {
  it("puts back the days the endpoint left out", () => {
    // The endpoint answers with a GROUP BY, so quiet days are absent, not
    // zero — charted as-is, two busy days fill the whole week.
    const filled = fillDailyGaps(
      [
        { timestamp: D10 + DAY, value: 2 },
        { timestamp: D10 + 2 * DAY, value: 5 },
      ],
      range,
      0,
    );
    expect(filled).toHaveLength(7);
    expect(filled.map((p) => p.value)).toEqual([0, 2, 5, 0, 0, 0, 0]);
  });

  it("keeps the days in order", () => {
    const filled = fillDailyGaps(
      [{ timestamp: D10 + 4 * DAY, value: 9 }],
      range,
      0,
    );
    const stamps = filled.map((p) => p.timestamp);
    expect([...stamps].sort((a, b) => a - b)).toEqual(stamps);
  });

  it("returns a full range when the endpoint returned nothing", () => {
    const filled = fillDailyGaps([], range, 0);
    expect(filled).toHaveLength(7);
    expect(filled.every((p) => p.value === 0)).toBe(true);
  });

  it("lines the filled days up with the real ones under an offset", () => {
    // Buenos Aires. A filled day landing half a day off would draw a bar
    // under the wrong label.
    const offset = -3;
    const midnight = D10 + 3 * 3600;
    const filled = fillDailyGaps(
      [{ timestamp: midnight + DAY, value: 4 }],
      { since: midnight, until: midnight + 3 * DAY },
      offset,
    );
    expect(filled.map((p) => p.timestamp)).toEqual([
      midnight,
      midnight + DAY,
      midnight + 2 * DAY,
      midnight + 3 * DAY,
    ]);
    expect(filled[1].value).toBe(4);
  });

  it("never drops a point that fell outside the window", () => {
    const stray = D10 - DAY;
    const filled = fillDailyGaps([{ timestamp: stray, value: 3 }], range, 0);
    expect(filled[0]).toEqual({ timestamp: stray, value: 3 });
  });

  it("does not overwrite a real zero with a filled one", () => {
    const filled = fillDailyGaps(
      [{ timestamp: D10, value: 0 }],
      { since: D10, until: D10 + DAY },
      0,
    );
    expect(filled).toHaveLength(2);
    expect(filled[0].value).toBe(0);
  });
});
