/**
 * A short two-note chime when a notification arrives, so a bot handoff or
 * a new assignment is heard even with AloStudio in a background tab.
 *
 * Synthesised with the Web Audio API (no audio file to load). On/off is a
 * per-device preference in localStorage, on by default. Browsers only let
 * a page make sound after the user interacted with it once; until then the
 * chime is skipped silently.
 */

export const NOTIFICATION_SOUND_KEY = "alostudio:notification-sound";

/** Several notifications in a burst (assignment + handoff) chime once. */
const MIN_GAP_MS = 1500;

let lastPlayed = 0;
let context: AudioContext | null = null;

export function isNotificationSoundOn(): boolean {
  try {
    return window.localStorage.getItem(NOTIFICATION_SOUND_KEY) !== "off";
  } catch {
    return true;
  }
}

export function setNotificationSoundOn(on: boolean): void {
  try {
    window.localStorage.setItem(NOTIFICATION_SOUND_KEY, on ? "on" : "off");
  } catch {
    // Private mode / storage blocked: the default (on) stays.
  }
}

function audioContext(): AudioContext | null {
  if (typeof window === "undefined") return null;
  const Ctor =
    window.AudioContext ??
    (window as unknown as { webkitAudioContext?: typeof AudioContext })
      .webkitAudioContext;
  if (!Ctor) return null;
  context ??= new Ctor();
  return context;
}

function tone(
  ctx: AudioContext,
  frequency: number,
  start: number,
  length: number,
) {
  const osc = ctx.createOscillator();
  const gain = ctx.createGain();
  osc.type = "sine";
  osc.frequency.value = frequency;
  // Quick attack, soft decay: audible without being harsh.
  gain.gain.setValueAtTime(0.0001, start);
  gain.gain.exponentialRampToValueAtTime(0.25, start + 0.02);
  gain.gain.exponentialRampToValueAtTime(0.0001, start + length);
  osc.connect(gain).connect(ctx.destination);
  osc.start(start);
  osc.stop(start + length + 0.05);
}

/**
 * Play the chime. ``force`` skips the on/off preference and the burst
 * guard (the "Probar" button). Never throws.
 */
export function playNotificationSound({ force = false } = {}): void {
  try {
    if (!force) {
      if (!isNotificationSoundOn()) return;
      const now = Date.now();
      if (now - lastPlayed < MIN_GAP_MS) return;
      lastPlayed = now;
    }
    const ctx = audioContext();
    if (!ctx) return;
    if (ctx.state === "suspended") void ctx.resume();
    const t = ctx.currentTime + 0.01;
    tone(ctx, 880, t, 0.18); // A5
    tone(ctx, 1318.5, t + 0.16, 0.3); // E6
  } catch {
    // No sound is better than a broken page.
  }
}

/** Test hook: forget the burst guard. */
export function resetNotificationSoundForTests(): void {
  lastPlayed = 0;
  context = null;
}
