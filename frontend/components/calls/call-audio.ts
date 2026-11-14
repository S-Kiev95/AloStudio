/**
 * The audio of a WhatsApp call, in the browser (F7).
 *
 * Meta sends the caller's WebRTC offer; we answer it here, so the audio goes
 * straight between Meta and this browser. Meta takes the answer whole (it
 * does not accept candidates sent later), so we wait for the browser to
 * gather them before handing it over. The microphone stays silent until
 * Meta confirms the call: the first words would otherwise be cut.
 */

const ICE_SERVERS: RTCIceServer[] = [{ urls: "stun:stun.l.google.com:19302" }];
const GATHER_TIMEOUT_MS = 3000;

export class MicrophoneBlocked extends Error {
  constructor() {
    super("microphone");
    this.name = "MicrophoneBlocked";
  }
}

export type CallAudio = {
  /** The answer for Meta (``pre_accept`` and ``accept`` get the same one). */
  answerSdp: string;
  /** Resolves true once the audio path with Meta is up, false on timeout. */
  waitConnected: (timeoutMs: number) => Promise<boolean>;
  /** Start sending the microphone (after Meta confirmed the call). */
  startSending: () => void;
  setMuted: (muted: boolean) => void;
  /** Called once if the connection drops for good. */
  onLost: (cb: () => void) => void;
  close: () => void;
};

function gathered(pc: RTCPeerConnection): Promise<void> {
  if (pc.iceGatheringState === "complete") return Promise.resolve();
  return new Promise((resolve) => {
    const done = () => {
      if (pc.iceGatheringState !== "complete") return;
      pc.removeEventListener("icegatheringstatechange", done);
      clearTimeout(timer);
      resolve();
    };
    // Some networks never report "complete"; what was gathered by then
    // is usually enough to reach Meta's public servers.
    const timer = setTimeout(() => {
      pc.removeEventListener("icegatheringstatechange", done);
      resolve();
    }, GATHER_TIMEOUT_MS);
    pc.addEventListener("icegatheringstatechange", done);
  });
}

/** Ask for the microphone and build the answer to the caller's offer. */
export async function answerOffer(
  offerSdp: string,
  speaker: HTMLAudioElement,
): Promise<CallAudio> {
  let stream: MediaStream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
  } catch {
    throw new MicrophoneBlocked();
  }
  const mic = stream.getAudioTracks()[0];
  const pc = new RTCPeerConnection({ iceServers: ICE_SERVERS });
  let muted = false;
  let live = false;
  let lost: (() => void) | null = null;
  let closed = false;

  pc.ontrack = (event) => {
    speaker.srcObject = event.streams[0] ?? new MediaStream([event.track]);
    void speaker.play().catch(() => undefined);
  };
  pc.onconnectionstatechange = () => {
    if (closed) return;
    if (pc.connectionState === "failed" || pc.connectionState === "closed") {
      const cb = lost;
      lost = null;
      cb?.();
    }
  };

  try {
    // Offer first, then the microphone: it then rides the offered audio
    // line instead of asking for a new one.
    await pc.setRemoteDescription({ type: "offer", sdp: offerSdp });
    if (mic) {
      mic.enabled = false;
      pc.addTrack(mic, stream);
    }
    const answer = await pc.createAnswer();
    await pc.setLocalDescription(answer);
    await gathered(pc);
  } catch (err) {
    stream.getTracks().forEach((track) => track.stop());
    pc.close();
    throw err;
  }

  const answerSdp = pc.localDescription?.sdp ?? "";

  return {
    answerSdp,
    waitConnected: (timeoutMs) =>
      new Promise((resolve) => {
        if (pc.connectionState === "connected") return resolve(true);
        const timer = setTimeout(() => {
          pc.removeEventListener("connectionstatechange", check);
          resolve(false);
        }, timeoutMs);
        const check = () => {
          if (pc.connectionState !== "connected") return;
          clearTimeout(timer);
          pc.removeEventListener("connectionstatechange", check);
          resolve(true);
        };
        pc.addEventListener("connectionstatechange", check);
      }),
    startSending: () => {
      live = true;
      if (mic) mic.enabled = !muted;
    },
    setMuted: (value) => {
      muted = value;
      if (mic && live) mic.enabled = !value;
    },
    onLost: (cb) => {
      lost = cb;
    },
    close: () => {
      if (closed) return;
      closed = true;
      stream.getTracks().forEach((track) => track.stop());
      pc.close();
      speaker.srcObject = null;
    },
  };
}

/** Two short tones every few seconds while a call rings. Browsers may keep
 *  the sound off until the page was clicked once; the card still shows. */
export function startRingtone(): () => void {
  type Ctor = typeof AudioContext;
  const AudioCtx: Ctor | undefined =
    typeof window === "undefined"
      ? undefined
      : window.AudioContext ??
        (window as unknown as { webkitAudioContext?: Ctor }).webkitAudioContext;
  if (!AudioCtx) return () => undefined;
  let ctx: AudioContext;
  try {
    ctx = new AudioCtx();
  } catch {
    return () => undefined;
  }
  void ctx.resume().catch(() => undefined);
  const beep = (at: number) => {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.value = 440;
    gain.gain.setValueAtTime(0.0001, at);
    gain.gain.exponentialRampToValueAtTime(0.18, at + 0.03);
    gain.gain.exponentialRampToValueAtTime(0.0001, at + 0.35);
    osc.connect(gain).connect(ctx.destination);
    osc.start(at);
    osc.stop(at + 0.4);
  };
  const ring = () => {
    const now = ctx.currentTime;
    beep(now);
    beep(now + 0.5);
  };
  ring();
  const timer = setInterval(ring, 3000);
  return () => {
    clearInterval(timer);
    void ctx.close().catch(() => undefined);
  };
}
