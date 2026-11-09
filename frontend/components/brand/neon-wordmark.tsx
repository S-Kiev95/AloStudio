"use client";

import Link from "next/link";
import { type CSSProperties, useEffect, useState } from "react";

import { cn } from "@/lib/utils";

const WORD = "AloStudio";
const LETTERS = Array.from(WORD);
const LAST_LETTER_INDEX = LETTERS.length - 1;
const IGNITE_FLICKERS: readonly ("1" | "2")[] = [
  "2",
  "1",
  "1",
  "2",
  "1",
  "2",
  "1",
  "1",
  "2",
];
const LETTER_STAGGER_MS = 65;
export const IGNITE_CLEAR_MS = 920;

export const SCENE_ORDER = [
  "breathe",
  "sequential",
  "last-o",
  "random-beat",
  "normal",
] as const;
export type NeonScene = (typeof SCENE_ORDER)[number];

export const BREATHE_DURATION_MS = 8_000;
export const NORMAL_DURATION_MS = 8_000;

export const SEQUENTIAL_DIM_MS = 300;
export const SEQUENTIAL_STEP_MS = 200;
export const SEQUENTIAL_PEAK_MS = 600;
export const SEQUENTIAL_DURATION_MS =
  SEQUENTIAL_DIM_MS + LETTERS.length * SEQUENTIAL_STEP_MS + SEQUENTIAL_PEAK_MS;

export const LAST_O_DURATION_MS = 5_000;

export const RANDOM_BEAT_DIM_MS = 300;
export const RANDOM_BEAT_PULSE_MS = 400;
export const RANDOM_BEAT_DOUBLE_CHANCE = 0.25;
export const RANDOM_BEAT_PEAK_MS = 400;

type TubeState = "off" | "lit" | "peak" | "last-o";

export interface NeonWordmarkProps {
  className?: string;
  href?: string;
  onClick?: () => void;
  as?: "span" | "div" | "p";
  /** When true, renders only the steady lit "A" monogram without scene loops. */
  collapsed?: boolean;
}

/**
 * Brand neon sign ("AloStudio").
 * Exposes the full word once to assistive technology via `aria-label="AloStudio"`
 * while rendering each glyph in an `aria-hidden` span so individual tubes can
 * ignite left-to-right (~900ms) and then loop through the five dark-mode brand
 * scenes (`breathe`, `sequential`, `last-o`, `random-beat`, `normal`) without
 * shifting layout or exceeding WCAG 2.3.1 (<= 3 flashes/s).
 */
export function NeonWordmark({
  className,
  href,
  onClick,
  as = "span",
  collapsed = false,
}: NeonWordmarkProps) {
  const [igniting, setIgniting] = useState(!collapsed);
  const [activeScene, setActiveScene] = useState<NeonScene | null>(null);
  const [tubeStates, setTubeStates] = useState<ReadonlyMap<number, TubeState>>(
    () => new Map(),
  );

  useEffect(() => {
    if (collapsed) {
      setIgniting(false);
      setActiveScene(null);
      setTubeStates((prev) => (prev.size === 0 ? prev : new Map()));
      return;
    }

    const timers = new Set<ReturnType<typeof setTimeout>>();
    let nextSceneIndex = 0;

    const schedule = (fn: () => void, ms: number) => {
      const id = setTimeout(() => {
        timers.delete(id);
        fn();
      }, ms);
      timers.add(id);
      return id;
    };

    const clearAll = () => {
      for (const id of timers) {
        clearTimeout(id);
      }
      timers.clear();
    };

    const mql =
      typeof window !== "undefined" && typeof window.matchMedia === "function"
        ? window.matchMedia("(prefers-reduced-motion: reduce)")
        : null;

    let seenDark =
      typeof document !== "undefined" &&
      document.documentElement.classList.contains("dark");

    const isReduced = () => Boolean(mql?.matches);
    const isLight = () => {
      if (typeof document === "undefined") return false;
      const cl = document.documentElement.classList;
      if (cl.contains("dark")) {
        seenDark = true;
        return false;
      }
      return cl.contains("light") || seenDark;
    };
    const isHidden = () =>
      typeof document !== "undefined" && document.hidden === true;

    let wasLight = isLight();

    if (isReduced() || wasLight || isHidden()) {
      setIgniting(false);
    } else {
      schedule(() => {
        setIgniting(false);
        startNextScene();
      }, IGNITE_CLEAR_MS);
    }

    const resetStates = () => {
      setActiveScene((prev) => (prev === null ? prev : null));
      setTubeStates((prev) => (prev.size === 0 ? prev : new Map()));
      setIgniting((prev) => (prev ? false : prev));
    };

    const finishScene = () => {
      resetStates();
      startNextScene();
    };

    const runScene = (scene: NeonScene) => {
      setActiveScene(scene);

      if (scene === "breathe") {
        setTubeStates(new Map());
        schedule(finishScene, BREATHE_DURATION_MS);
        return;
      }

      if (scene === "normal") {
        setTubeStates(new Map());
        schedule(finishScene, NORMAL_DURATION_MS);
        return;
      }

      if (scene === "sequential") {
        setTubeStates(new Map(LETTERS.map((_, i) => [i, "off"])));
        for (let i = 0; i < LETTERS.length; i += 1) {
          schedule(
            () => {
              setTubeStates((prev) => {
                const next = new Map(prev);
                next.set(i, "lit");
                return next;
              });
            },
            SEQUENTIAL_DIM_MS + i * SEQUENTIAL_STEP_MS,
          );
        }
        schedule(
          () => {
            setTubeStates(new Map(LETTERS.map((_, i) => [i, "peak"])));
          },
          SEQUENTIAL_DIM_MS + LETTERS.length * SEQUENTIAL_STEP_MS,
        );
        schedule(finishScene, SEQUENTIAL_DURATION_MS);
        return;
      }

      if (scene === "last-o") {
        setTubeStates(new Map([[LAST_LETTER_INDEX, "last-o"]]));
        schedule(finishScene, LAST_O_DURATION_MS);
        return;
      }

      // scene === "random-beat"
      setTubeStates(new Map(LETTERS.map((_, i) => [i, "off"])));
      const remaining = LETTERS.map((_, i) => i);

      const stepPulse = () => {
        if (isReduced() || isLight() || isHidden()) return;
        const count =
          remaining.length >= 2 && Math.random() < RANDOM_BEAT_DOUBLE_CHANCE
            ? 2
            : 1;
        const picked: number[] = [];
        for (let step = 0; step < count && remaining.length > 0; step += 1) {
          const randomIdx = Math.floor(Math.random() * remaining.length);
          const [letterIdx] = remaining.splice(randomIdx, 1);
          if (letterIdx !== undefined) {
            picked.push(letterIdx);
          }
        }
        setTubeStates((prev) => {
          const next = new Map(prev);
          for (const idx of picked) {
            next.set(idx, "lit");
          }
          return next;
        });

        if (remaining.length > 0) {
          schedule(stepPulse, RANDOM_BEAT_PULSE_MS);
        } else {
          schedule(() => {
            setTubeStates(new Map(LETTERS.map((_, i) => [i, "peak"])));
            schedule(finishScene, RANDOM_BEAT_PEAK_MS);
          }, RANDOM_BEAT_PULSE_MS);
        }
      };

      schedule(stepPulse, RANDOM_BEAT_DIM_MS);
    };

    function startNextScene() {
      if (isReduced() || isLight() || isHidden()) return;
      const scene = SCENE_ORDER[nextSceneIndex];
      nextSceneIndex = (nextSceneIndex + 1) % SCENE_ORDER.length;
      runScene(scene);
    }

    const resetAndReschedule = () => {
      clearAll();
      resetStates();
      startNextScene();
    };

    const handleClassMutation = () => {
      const nowLight = isLight();
      if (nowLight === wasLight) return;
      wasLight = nowLight;
      resetAndReschedule();
    };

    document.addEventListener("visibilitychange", resetAndReschedule);
    mql?.addEventListener?.("change", resetAndReschedule);

    const observer =
      typeof MutationObserver !== "undefined"
        ? new MutationObserver(handleClassMutation)
        : null;
    observer?.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["class"],
    });

    return () => {
      clearAll();
      document.removeEventListener("visibilitychange", resetAndReschedule);
      mql?.removeEventListener?.("change", resetAndReschedule);
      observer?.disconnect();
    };
  }, [collapsed]);

  const mergedClassName = cn(
    "neon-wordmark neon-wordmark-live inline-block select-none text-[36px] leading-none",
    !collapsed && igniting && "neon-wordmark-ignite",
    className,
  );

  const rootStyle =
    !collapsed && activeScene
      ? ({
          "--scene-duration": `${
            activeScene === "breathe"
              ? BREATHE_DURATION_MS
              : activeScene === "last-o"
                ? LAST_O_DURATION_MS
                : SEQUENTIAL_DURATION_MS
          }ms`,
          "--peak-duration": `${
            activeScene === "random-beat"
              ? RANDOM_BEAT_PEAK_MS
              : SEQUENTIAL_PEAK_MS
          }ms`,
        } as CSSProperties)
      : undefined;

  const letters = collapsed ? (
    <span aria-hidden="true" className="neon-wordmark-letter">
      {LETTERS[0]}
    </span>
  ) : (
    LETTERS.map((char, index) => {
      const tubeState = tubeStates.get(index);
      const style = {
        "--letter-delay": `${index * LETTER_STAGGER_MS}ms`,
      } as CSSProperties;

      return (
        <span
          key={index}
          aria-hidden="true"
          data-ignite={IGNITE_FLICKERS[index]}
          data-tube={tubeState}
          style={style}
          className="neon-wordmark-letter"
        >
          {char}
        </span>
      );
    })
  );

  const sceneAttr = collapsed ? undefined : (activeScene ?? undefined);

  if (href) {
    return (
      <Link
        href={href}
        onClick={onClick}
        aria-label={WORD}
        data-scene={sceneAttr}
        style={rootStyle}
        className={mergedClassName}
      >
        {letters}
      </Link>
    );
  }

  const Tag = as;
  return (
    <Tag
      role="img"
      aria-label={WORD}
      onClick={onClick}
      data-scene={sceneAttr}
      style={rootStyle}
      className={mergedClassName}
    >
      {letters}
    </Tag>
  );
}
