"use client";

import Link from "next/link";
import { type CSSProperties, useEffect, useState } from "react";

import { cn } from "@/lib/utils";

const WORD = "AloStudio";
const LETTERS = Array.from(WORD);
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
const IGNITE_CLEAR_MS = 920;
const BUZZ_MIN_INTERVAL_MS = 15_000;
const BUZZ_MAX_INTERVAL_MS = 45_000;
const BUZZ_MIN_DURATION_MS = 150;
const BUZZ_MAX_DURATION_MS = 400;

type BuzzKind = "single" | "double";

interface LetterBuzz {
  kind: BuzzKind;
  durationMs: number;
  delayMs: number;
}

export interface NeonWordmarkProps {
  className?: string;
  href?: string;
  onClick?: () => void;
  as?: "span" | "div" | "p";
}

/**
 * Brand neon sign ("AloStudio").
 * Exposes the full word once to assistive technology via `aria-label="AloStudio"`
 * while rendering each glyph in an `aria-hidden` span so individual tubes can
 * ignite left-to-right (~900ms) and occasionally hum/flicker in dark mode
 * without shifting layout or exceeding WCAG 2.3.1 (<= 3 flashes/s).
 */
export function NeonWordmark({
  className,
  href,
  onClick,
  as = "span",
}: NeonWordmarkProps) {
  const [igniting, setIgniting] = useState(true);
  const [activeBuzz, setActiveBuzz] = useState<ReadonlyMap<number, LetterBuzz>>(
    () => new Map(),
  );

  useEffect(() => {
    const timers = new Set<ReturnType<typeof setTimeout>>();

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

    const isReduced = () => Boolean(mql?.matches);
    const isLight = () =>
      typeof document !== "undefined" &&
      document.documentElement.classList.contains("light") &&
      !document.documentElement.classList.contains("dark");
    const isHidden = () =>
      typeof document !== "undefined" && document.hidden === true;

    let wasLight = isLight();

    if (isReduced() || wasLight) {
      setIgniting(false);
    } else {
      schedule(() => {
        setIgniting(false);
      }, IGNITE_CLEAR_MS);
    }

    const scheduleNextBuzz = () => {
      if (isReduced() || isLight() || isHidden()) return;
      const waitMs = Math.round(
        BUZZ_MIN_INTERVAL_MS +
          Math.random() * (BUZZ_MAX_INTERVAL_MS - BUZZ_MIN_INTERVAL_MS),
      );
      schedule(() => {
        if (isReduced() || isLight() || isHidden()) return;

        const twoLetters = Math.random() < 0.25;
        const nextBuzz = new Map<number, LetterBuzz>();

        if (twoLetters) {
          const first = Math.floor(Math.random() * (LETTERS.length - 1));
          const durationMs = Math.round(180 + Math.random() * 170);
          const secondDelay = 45;
          nextBuzz.set(first, { kind: "single", durationMs, delayMs: 0 });
          nextBuzz.set(first + 1, {
            kind: "single",
            durationMs,
            delayMs: secondDelay,
          });
          setActiveBuzz(nextBuzz);
          schedule(() => {
            setActiveBuzz(new Map());
            scheduleNextBuzz();
          }, durationMs + secondDelay + 20);
        } else {
          const index = Math.floor(Math.random() * LETTERS.length);
          const kind: BuzzKind = Math.random() < 0.35 ? "double" : "single";
          const minDur = kind === "double" ? 260 : BUZZ_MIN_DURATION_MS;
          const durationMs = Math.round(
            minDur + Math.random() * (BUZZ_MAX_DURATION_MS - minDur),
          );
          nextBuzz.set(index, { kind, durationMs, delayMs: 0 });
          setActiveBuzz(nextBuzz);
          schedule(() => {
            setActiveBuzz(new Map());
            scheduleNextBuzz();
          }, durationMs + 20);
        }
      }, waitMs);
    };

    scheduleNextBuzz();

    const resetAndReschedule = () => {
      clearAll();
      setActiveBuzz(new Map());
      setIgniting(false);
      if (!isReduced() && !isLight() && !isHidden()) {
        scheduleNextBuzz();
      }
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
  }, []);

  const mergedClassName = cn(
    "neon-wordmark neon-wordmark-live inline-block select-none text-[36px] leading-none",
    igniting && "neon-wordmark-ignite",
    className,
  );

  const letters = LETTERS.map((char, index) => {
    const buzz = activeBuzz.get(index);
    const style = {
      "--letter-delay": `${index * LETTER_STAGGER_MS}ms`,
      ...(buzz
        ? {
            "--buzz-duration": `${buzz.durationMs}ms`,
            "--buzz-delay": `${buzz.delayMs}ms`,
          }
        : null),
    } as CSSProperties;

    return (
      <span
        key={index}
        aria-hidden="true"
        data-ignite={IGNITE_FLICKERS[index]}
        data-buzz={buzz?.kind}
        style={style}
        className="neon-wordmark-letter"
      >
        {char}
      </span>
    );
  });

  if (href) {
    return (
      <Link
        href={href}
        onClick={onClick}
        aria-label={WORD}
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
      className={mergedClassName}
    >
      {letters}
    </Tag>
  );
}
