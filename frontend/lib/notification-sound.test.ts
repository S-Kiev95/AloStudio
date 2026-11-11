import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  NOTIFICATION_SOUND_KEY,
  isNotificationSoundOn,
  playNotificationSound,
  resetNotificationSoundForTests,
  setNotificationSoundOn,
} from "./notification-sound";

/** Minimal Web Audio stand-in: counts the notes scheduled. */
function fakeAudio() {
  const started: number[] = [];
  class FakeContext {
    state = "running";
    currentTime = 0;
    destination = {};
    resume = vi.fn();
    createOscillator() {
      return {
        type: "sine",
        frequency: { value: 0 },
        connect: (node: unknown) => node,
        start: (t: number) => started.push(t),
        stop: vi.fn(),
      };
    }
    createGain() {
      const gain = {
        gain: {
          setValueAtTime: vi.fn(),
          exponentialRampToValueAtTime: vi.fn(),
        },
        connect: (node: unknown) => node,
      };
      return gain;
    }
  }
  vi.stubGlobal("AudioContext", FakeContext);
  return started;
}

describe("notification sound", () => {
  beforeEach(() => {
    window.localStorage.clear();
    resetNotificationSoundForTests();
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("is on by default and remembers the choice", () => {
    expect(isNotificationSoundOn()).toBe(true);
    setNotificationSoundOn(false);
    expect(window.localStorage.getItem(NOTIFICATION_SOUND_KEY)).toBe("off");
    expect(isNotificationSoundOn()).toBe(false);
  });

  it("plays a two-note chime", () => {
    const started = fakeAudio();
    playNotificationSound();
    expect(started).toHaveLength(2);
  });

  it("stays quiet when turned off, unless forced by the test button", () => {
    const started = fakeAudio();
    setNotificationSoundOn(false);
    playNotificationSound();
    expect(started).toHaveLength(0);
    playNotificationSound({ force: true });
    expect(started).toHaveLength(2);
  });

  it("chimes once for a burst of notifications", () => {
    vi.useFakeTimers();
    const started = fakeAudio();
    playNotificationSound();
    playNotificationSound();
    expect(started).toHaveLength(2);
    vi.advanceTimersByTime(2000);
    playNotificationSound();
    expect(started).toHaveLength(4);
  });

  it("never throws when the browser has no Web Audio", () => {
    vi.stubGlobal("AudioContext", undefined);
    expect(() => playNotificationSound()).not.toThrow();
  });
});
