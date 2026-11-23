"use client";

import { type RefObject, useEffect, useRef } from "react";

/**
 * Dismisses an open popover or menu when the user clicks/taps outside `ref`
 * or presses Escape. Keeps the latest `onClose` callback in a ref so callers
 * can pass inline functions without re-attaching document listeners.
 */
export function useDismissOnOutsideAndEscape(
  ref: RefObject<HTMLElement | null>,
  open: boolean,
  onClose: () => void,
  options?: { stopEscapePropagation?: boolean },
): void {
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  const stopEscape = options?.stopEscapePropagation ?? false;

  useEffect(() => {
    if (!open) return;

    function handlePointer(e: MouseEvent | TouchEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onCloseRef.current();
      }
    }

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        if (stopEscape) {
          e.preventDefault();
          e.stopPropagation();
        }
        onCloseRef.current();
      }
    }

    document.addEventListener("mousedown", handlePointer);
    document.addEventListener("touchstart", handlePointer);
    document.addEventListener("keydown", handleKeyDown, stopEscape);
    return () => {
      document.removeEventListener("mousedown", handlePointer);
      document.removeEventListener("touchstart", handlePointer);
      document.removeEventListener("keydown", handleKeyDown, stopEscape);
    };
  }, [ref, open, stopEscape]);
}
