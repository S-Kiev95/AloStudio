import { afterEach, describe, expect, it, vi } from "vitest";

import { relativeTime } from "./time";

afterEach(() => vi.useRealTimers());

describe("relativeTime", () => {
  function at(now: string) {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(now));
  }
  const unix = (iso: string) => Math.floor(new Date(iso).getTime() / 1000);

  it("returns empty for null", () => {
    expect(relativeTime(null)).toBe("");
  });

  it("says 'ahora' under a minute", () => {
    at("2026-01-01T12:00:30Z");
    expect(relativeTime(unix("2026-01-01T12:00:00Z"))).toBe("ahora");
  });

  it("formats minutes", () => {
    at("2026-01-01T12:05:00Z");
    expect(relativeTime(unix("2026-01-01T12:00:00Z"))).toBe("hace 5m");
  });

  it("formats hours", () => {
    at("2026-01-01T15:00:00Z");
    expect(relativeTime(unix("2026-01-01T12:00:00Z"))).toBe("hace 3h");
  });
});
