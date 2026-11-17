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

type Line = {
  pc: RTCPeerConnection;
  stream: MediaStream;
  mic: MediaStreamTrack | undefined;
  /** Everything a call needs once the descriptions are set. */
  controls: Omit<CallAudio, "answerSdp">;
};

/** The microphone and a peer connection that plays the other side. The
 *  microphone stays silent until :func:`startSending`. */
async function openLine(speaker: HTMLAudioElement): Promise<Line> {
  let stream: MediaStream;
  try {
    stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
  } catch {
    throw new MicrophoneBlocked();
  }
  const mic = stream.getAudioTracks()[0];
  if (mic) mic.enabled = false;
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

  const controls: Omit<CallAudio, "answerSdp"> = {
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
  return { pc, stream, mic, controls };
}

/** Ask for the microphone and build the answer to the caller's offer. */
export async function answerOffer(
  offerSdp: string,
  speaker: HTMLAudioElement,
): Promise<CallAudio> {
  const { pc, stream, mic, controls } = await openLine(speaker);
  try {
    // Offer first, then the microphone: it then rides the offered audio
    // line instead of asking for a new one.
    await pc.setRemoteDescription({ type: "offer", sdp: offerSdp });
    if (mic) pc.addTrack(mic, stream);
    const answer = await pc.createAnswer();
    await pc.setLocalDescription(answer);
    await gathered(pc);
  } catch (err) {
    controls.close();
    throw err;
  }
  return { ...controls, answerSdp: pc.localDescription?.sdp ?? "" };
}

/** A call we make: the offer for Meta, and where the customer's answer goes
 *  when it arrives. */
export type OutgoingAudio = Omit<CallAudio, "answerSdp"> & {
  offerSdp: string;
  applyAnswer: (sdp: string) => Promise<void>;
};

export async function placeCall(speaker: HTMLAudioElement): Promise<OutgoingAudio> {
  const { pc, stream, mic, controls } = await openLine(speaker);
  try {
    if (mic) pc.addTrack(mic, stream);
    else pc.addTransceiver("audio", { direction: "recvonly" });
    const offer = await pc.createOffer();
    await pc.setLocalDescription(offer);
    await gathered(pc);
  } catch (err) {
    controls.close();
    throw err;
  }
  return {
    ...controls,
    offerSdp: pc.localDescription?.sdp ?? "",
    applyAnswer: async (sdp) => {
      if (pc.signalingState === "have-local-offer") {
        await pc.setRemoteDescription({ type: "answer", sdp });
      }
    },
  };
}

/** Two short tones every few seconds while a call rings. Browsers may keep
 *  the sound off until the page was clicked once; the card still shows. */
/** Two beeps every 3 s; while I am on another call (``waiting``), one soft
 *  beep every 6 s, like call waiting on a phone. */
export function startRingtone(waiting = false): () => void {
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
    gain.gain.exponentialRampToValueAtTime(waiting ? 0.06 : 0.18, at + 0.03);
    gain.gain.exponentialRampToValueAtTime(0.0001, at + 0.35);
    osc.connect(gain).connect(ctx.destination);
    osc.start(at);
    osc.stop(at + 0.4);
  };
  const ring = () => {
    const now = ctx.currentTime;
    beep(now);
    if (!waiting) beep(now + 0.5);
  };
  ring();
  const timer = setInterval(ring, waiting ? 6000 : 3000);
  return () => {
    clearInterval(timer);
    void ctx.close().catch(() => undefined);
  };
}
