"use client";

import { animate, createTimeline, stagger } from "animejs";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type MutableRefObject,
  type ReactNode,
} from "react";

import { NEON_ENTER_MS, prefersReducedMotion } from "@/lib/motion/neon-motion";
import { cn } from "@/lib/utils";

/** Total duration of the black-hole login transition (~5 seconds). */
export const BLACK_HOLE_DURATION_MS = 5000;
/** Simple fade duration when `prefers-reduced-motion: reduce` is active. */
export const REDUCED_TRANSITION_MS = NEON_ENTER_MS;

export interface BlackHoleState {
  active: boolean;
  /** 0..1 accretion disk brightness */
  disk: number;
  /** 0..1 pitch-black event horizon opacity */
  horizon: number;
  /** 0..1 spaghettification pull on 3D FloatingLogos */
  pull: number;
  /** 0..1 final camera plunge into the singularity */
  dive: number;
  /** 0..1 blackout veil right before entering Inicio */
  veil: number;
  /** Card center in viewport CSS px */
  cx: number;
  cy: number;
  /** Event horizon base radius in CSS px */
  radius: number;
}

export interface AuthSingularityContextValue {
  status: "idle" | "active" | "reduced";
  stateRef: MutableRefObject<BlackHoleState>;
  registerWebGL: (ready: boolean) => void;
  triggerBlackHole: (onComplete: () => void) => void;
}

const AuthSingularityContext =
  createContext<AuthSingularityContextValue | null>(null);

export function useAuthSingularity(): AuthSingularityContextValue | null {
  return useContext(AuthSingularityContext);
}

const INITIAL_STATE: BlackHoleState = {
  active: false,
  disk: 0,
  horizon: 0,
  pull: 0,
  dive: 0,
  veil: 0,
  cx: 0,
  cy: 0,
  radius: 72,
};

/** Deterministic per-shard fracture vectors (matches approved prototype). */
const SHARD_VECTORS = [
  { rot: -26, skew: 12, dx: -24 },
  { rot: 18, skew: -10, dx: 18 },
  { rot: -14, skew: 8, dx: -16 },
  { rot: 24, skew: -14, dx: 28 },
  { rot: -22, skew: 14, dx: -26 },
  { rot: 30, skew: -16, dx: 14 },
  { rot: -18, skew: 10, dx: -10 },
  { rot: 20, skew: -12, dx: 20 },
];

export function AuthSingularityShell({
  children,
  topControls,
  background,
  wordmark,
}: {
  children: ReactNode;
  topControls: ReactNode;
  background: ReactNode;
  wordmark: ReactNode;
}) {
  const [status, setStatus] = useState<"idle" | "active" | "reduced">("idle");
  const [webglReady, setWebglReady] = useState(false);

  const stateRef = useRef<BlackHoleState>({ ...INITIAL_STATE });
  const rigRef = useRef<HTMLDivElement>(null);
  const cardRef = useRef<HTMLDivElement>(null);
  const shellRef = useRef<HTMLDivElement>(null);
  const cracksRef = useRef<SVGSVGElement>(null);
  const fallbackDiskRef = useRef<HTMLDivElement>(null);
  const veilRef = useRef<HTMLDivElement>(null);
  const runningRef = useRef(false);
  const cancelRef = useRef<(() => void) | null>(null);

  const registerWebGL = useCallback((ready: boolean) => {
    setWebglReady(ready);
  }, []);

  useEffect(() => {
    return () => {
      cancelRef.current?.();
      cancelRef.current = null;
    };
  }, []);

  const triggerBlackHole = useCallback((onComplete: () => void) => {
    if (runningRef.current) return;
    runningRef.current = true;

    let completed = false;
    const finish = () => {
      if (completed) return;
      completed = true;
      onComplete();
    };

    if (prefersReducedMotion()) {
      setStatus("reduced");
      const target = rigRef.current ?? cardRef.current;
      if (target) {
        const anim = animate(target, {
          opacity: [1, 0],
          duration: REDUCED_TRANSITION_MS,
          ease: "outCubic",
          onComplete: finish,
        });
        const safety = window.setTimeout(finish, REDUCED_TRANSITION_MS + 80);
        cancelRef.current = () => {
          window.clearTimeout(safety);
          anim.cancel();
        };
      } else {
        const timer = window.setTimeout(finish, REDUCED_TRANSITION_MS);
        cancelRef.current = () => window.clearTimeout(timer);
      }
      return;
    }

    setStatus("active");

    const cardEl = cardRef.current;
    const shellEl = shellRef.current;
    const rigEl = rigRef.current;
    const cracksEl = cracksRef.current;
    const veilEl = veilRef.current;
    const fallbackDiskEl = fallbackDiskRef.current;

    const vw = typeof window !== "undefined" ? window.innerWidth : 1280;
    const vh = typeof window !== "undefined" ? window.innerHeight : 800;
    const rect = cardEl?.getBoundingClientRect() ?? {
      left: vw / 2 - 210,
      top: vh / 2 - 245,
      width: 420,
      height: 490,
      right: vw / 2 + 210,
      bottom: vh / 2 + 245,
    };
    const cx = rect.width > 0 ? rect.left + rect.width / 2 : vw / 2;
    const cy = rect.height > 0 ? rect.top + rect.height / 2 : vh / 2;
    const radius = Math.min(76, Math.max(52, vw * 0.19));

    const st = stateRef.current;
    st.active = true;
    st.disk = 0;
    st.horizon = 0;
    st.pull = 0;
    st.dive = 0;
    st.veil = 0;
    st.cx = cx;
    st.cy = cy;
    st.radius = radius;

    const tl = createTimeline({
      autoplay: true,
      onComplete: finish,
    });

    // 1. Cracks flash on the glass panel (0 -> 1320ms)
    if (cracksEl) {
      tl.add(
        cracksEl,
        {
          opacity: [0, 0.92, 0],
          duration: 1320,
          ease: "inOutQuad",
        },
        0,
      );
    }

    // 2. Form fields & elements fracture and fall toward card center (0 -> 1600ms)
    const shards = cardEl
      ? Array.from(cardEl.querySelectorAll<HTMLElement>("[data-bh-shard]"))
      : [];

    shards.forEach((el, idx) => {
      const cfg = SHARD_VECTORS[idx % SHARD_VECTORS.length]!;
      const er = el.getBoundingClientRect();
      const targetX =
        er.width > 0 ? cx - (er.left + er.width / 2) : -cfg.dx;
      const targetY =
        er.height > 0 ? cy - (er.top + er.height / 2) : (idx - 3) * -42;

      tl.add(
        el,
        {
          translateX: [0, targetX],
          translateY: [0, targetY],
          rotate: [0, cfg.rot],
          skewX: [0, cfg.skew],
          scale: [1, 0.08],
          opacity: [1, 0],
          duration: 1120,
          ease: "inExpo",
        },
        idx * 68,
      );
    });

    // 3. Card shell contracts into a pitch-black sphere with cobalt rim (320 -> 1800ms)
    if (shellEl) {
      const cardW = rect.width > 0 ? rect.width : 420;
      const cardH = rect.height > 0 ? rect.height : 490;
      const sx = (radius * 2) / cardW;
      const sy = (radius * 2) / cardH;

      tl.add(
        shellEl,
        {
          scaleX: [1, sx],
          scaleY: [1, sy],
          borderRadius: ["16px", "999px"],
          backgroundColor: "#000000",
          boxShadow:
            "inset 0 0 0 2px rgba(219, 228, 255, 0.9), 0 0 44px rgba(61, 107, 255, 0.78)",
          duration: 1280,
          ease: "inOutCubic",
        },
        320,
      );
      tl.add(
        shellEl,
        {
          opacity: [1, 0],
          duration: 440,
          ease: "outQuad",
        },
        1360,
      );
    }

    // 4. Shared Anime.js v4 state driving Three.js accretion disk, gum stretch & dive
    tl.add(
      st,
      {
        disk: [0, 1],
        duration: 1360,
        ease: "outExpo",
      },
      720,
    );
    tl.add(
      st,
      {
        horizon: [0, 1],
        duration: 600,
        ease: "outQuad",
      },
      880,
    );
    tl.add(
      st,
      {
        pull: [0, 1],
        duration: 2760,
        ease: "inOutQuad",
      },
      960,
    );
    tl.add(
      st,
      {
        dive: [0, 1],
        duration: 1320,
        ease: "inExpo",
      },
      3600,
    );
    tl.add(
      st,
      {
        veil: [0, 1],
        duration: 920,
        ease: "inCubic",
      },
      4000,
    );

    // CSS fallback accretion disk when WebGL is unavailable
    if (fallbackDiskEl) {
      tl.add(
        fallbackDiskEl,
        {
          opacity: [0, 1],
          scale: [0.35, 1],
          duration: 1280,
          ease: "outExpo",
        },
        760,
      );
      tl.add(
        fallbackDiskEl,
        {
          scale: [1, 10],
          duration: 1320,
          ease: "inExpo",
        },
        3600,
      );
    }

    // 5. Camera rig plunge + final blackout veil (3640 -> 5000ms)
    if (rigEl) {
      tl.add(
        rigEl,
        {
          scale: [1, 4.2],
          opacity: [1, 0],
          duration: 1280,
          ease: "inExpo",
        },
        3640,
      );
    }
    if (veilEl) {
      tl.add(
        veilEl,
        {
          opacity: [0, 1],
          duration: 880,
          ease: "inCubic",
        },
        4040,
      );
    }

    // Safety cap so navigation never hangs if rAF is throttled
    const safety = window.setTimeout(finish, BLACK_HOLE_DURATION_MS + 350);
    cancelRef.current = () => {
      window.clearTimeout(safety);
      tl.cancel();
    };
  }, []);

  const ctxValue = useMemo<AuthSingularityContextValue>(
    () => ({
      status,
      stateRef,
      registerWebGL,
      triggerBlackHole,
    }),
    [status, registerWebGL, triggerBlackHole],
  );

  // Use stagger import meaningfully to compute subtle crack-line reveal helper if needed
  void stagger;

  return (
    <AuthSingularityContext.Provider value={ctxValue}>
      <div
        data-singularity={status}
        className="relative flex min-h-dvh flex-col items-center justify-center overflow-hidden p-4 sm:p-6"
      >
        <div
          className={cn(
            "fixed right-3 top-3 z-20 flex items-center gap-1 transition-opacity duration-200",
            status !== "idle" && "pointer-events-none opacity-0",
          )}
        >
          {topControls}
        </div>

        {background}

        {/* CSS fallback accretion disk when WebGL is disabled/unavailable */}
        {!webglReady && status === "active" ? (
          <div
            ref={fallbackDiskRef}
            aria-hidden
            className="pointer-events-none fixed left-1/2 top-1/2 z-10 h-44 w-44 -translate-x-1/2 -translate-y-1/2 rounded-full opacity-0"
            style={{
              background:
                "radial-gradient(circle, #000000 0%, #000000 38%, rgba(219,228,255,0.95) 42%, rgba(61,107,255,0.78) 54%, rgba(29,78,216,0.25) 75%, transparent 100%)",
              boxShadow: "0 0 60px rgba(61, 107, 255, 0.7)",
            }}
          />
        ) : null}

        <div
          ref={rigRef}
          className="relative z-10 flex w-full items-center justify-center will-change-transform"
        >
          <div
            ref={cardRef}
            data-bounce
            className="page-enter relative w-full max-w-[420px] rounded-panel p-7 sm:p-9"
          >
            {/* Card shell that morphs into the pitch-black event horizon sphere */}
            <div
              ref={shellRef}
              data-bh-shell
              aria-hidden
              className="glass-panel pointer-events-none absolute inset-0 z-0 rounded-panel"
            />

            {/* Cobalt fracture cracks overlay (visible only during Phase 1) */}
            <svg
              ref={cracksRef}
              aria-hidden
              viewBox="0 0 420 490"
              preserveAspectRatio="none"
              className="pointer-events-none absolute inset-0 z-[3] h-full w-full opacity-0"
            >
              <g
                stroke="var(--neon-core)"
                strokeWidth="1.4"
                fill="none"
                strokeLinecap="round"
              >
                <path d="M210 245 L142 158 L80 112 M142 158 L168 62" />
                <path d="M210 245 L292 170 L368 122 M292 170 L270 72" />
                <path d="M210 245 L136 332 L68 408 M136 332 L182 448" />
                <path d="M210 245 L296 320 L372 396 M296 320 L254 446" />
                <path d="M210 245 L56 248 M210 245 L368 232" opacity="0.65" />
              </g>
            </svg>

            <div className="relative z-[2]">
              <div data-bh-shard className="mb-7">
                {wordmark}
              </div>
              {children}
            </div>
          </div>
        </div>

        {/* Final blackout veil before landing in AloStudio Inicio */}
        <div
          ref={veilRef}
          aria-hidden
          className="pointer-events-none fixed inset-0 z-30 opacity-0"
          style={{ backgroundColor: "#02040c" }}
        />
      </div>
    </AuthSingularityContext.Provider>
  );
}
