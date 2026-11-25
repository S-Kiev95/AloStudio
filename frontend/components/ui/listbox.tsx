"use client";

import { Check, ChevronDown } from "lucide-react";
import {
  type KeyboardEvent,
  type ReactNode,
  useCallback,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";

import { animatePopoverIn } from "@/lib/motion/neon-motion";
import { cn } from "@/lib/utils";

export interface ListboxOption<T extends string = string> {
  value: T;
  label: string;
  /** BCP-47 language tag applied to the option label (e.g. `"es"`, `"ja"`). */
  lang?: string;
  disabled?: boolean;
}

export interface ListboxProps<T extends string = string> {
  value: T;
  onChange: (value: T) => void;
  options: readonly ListboxOption<T>[];
  id?: string;
  name?: string;
  disabled?: boolean;
  placeholder?: string;
  /**
   * - `"field"` matches `<Select>` inside forms (recessed `.glass-field`).
   * - `"compact"` fits topbar and auth utility controls.
   */
  variant?: "field" | "compact";
  size?: "sm" | "md";
  /** Preferred horizontal edge to anchor the popup to. Clamped to viewport. */
  align?: "start" | "end";
  /** Optional icon placed before the selected label inside the trigger. */
  leadingIcon?: ReactNode;
  "aria-label"?: string;
  "aria-labelledby"?: string;
  "aria-describedby"?: string;
  "aria-invalid"?: boolean | "true" | "false";
  className?: string;
  listClassName?: string;
}

interface MenuPosition {
  top?: number;
  bottom?: number;
  left: number;
  minWidth: number;
  maxHeight: number;
  placement: "down" | "up";
}

const VIEWPORT_MARGIN = 8;
const MENU_GAP = 6;
const MAX_MENU_HEIGHT = 280;
const TYPEAHEAD_RESET_MS = 500;
const PAGE_STEP = 5;

const useIsomorphicLayoutEffect =
  typeof window !== "undefined" ? useLayoutEffect : useEffect;

function normalizeForSearch(text: string): string {
  return text
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase();
}

function findFirstEnabledIndex<T extends string>(
  options: readonly ListboxOption<T>[],
): number {
  return options.findIndex((o) => !o.disabled);
}

function findLastEnabledIndex<T extends string>(
  options: readonly ListboxOption<T>[],
): number {
  for (let i = options.length - 1; i >= 0; i -= 1) {
    if (!options[i]?.disabled) return i;
  }
  return -1;
}

function findNextEnabledIndex<T extends string>(
  options: readonly ListboxOption<T>[],
  from: number,
  step: number,
): number {
  if (options.length === 0) return -1;
  const dir = step >= 0 ? 1 : -1;
  const distance = Math.abs(step);
  let idx = from;
  let moved = 0;

  for (let i = from + dir; i >= 0 && i < options.length; i += dir) {
    if (!options[i]?.disabled) {
      idx = i;
      moved += 1;
      if (moved >= distance) break;
    }
  }
  return idx;
}

function findTypeaheadMatch<T extends string>(
  options: readonly ListboxOption<T>[],
  query: string,
  startFrom: number,
): number {
  const needle = normalizeForSearch(query);
  if (!needle || options.length === 0) return -1;

  for (let offset = 0; offset < options.length; offset += 1) {
    const idx = (startFrom + offset + options.length) % options.length;
    const opt = options[idx];
    if (!opt || opt.disabled) continue;
    if (normalizeForSearch(opt.label).startsWith(needle)) {
      return idx;
    }
  }
  return -1;
}

/**
 * Custom accessible select-only combobox following the WAI-ARIA APG pattern
 * and AloStudio's "Hand-Bent Neon Room" design system. Portals its popup so
 * it escapes `overflow-hidden` and `view-transition-name` stacking contexts.
 */
export function Listbox<T extends string = string>({
  value,
  onChange,
  options,
  id,
  name,
  disabled = false,
  placeholder,
  variant = "field",
  size = "md",
  align = "start",
  leadingIcon,
  "aria-label": ariaLabel,
  "aria-labelledby": ariaLabelledBy,
  "aria-describedby": ariaDescribedBy,
  "aria-invalid": ariaInvalid,
  className,
  listClassName,
}: ListboxProps<T>) {
  const generatedId = useId();
  const baseId = id ?? generatedId;
  const listboxId = `${baseId}-listbox`;

  const triggerRef = useRef<HTMLButtonElement>(null);
  const listRef = useRef<HTMLUListElement>(null);
  const optionRefs = useRef<Array<HTMLLIElement | null>>([]);
  const typeaheadRef = useRef<{ buffer: string; timer: number | null }>({
    buffer: "",
    timer: null,
  });

  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const [position, setPosition] = useState<MenuPosition | null>(null);

  const selectedIndex = useMemo(
    () => options.findIndex((o) => o.value === value),
    [options, value],
  );
  const selectedOption = selectedIndex >= 0 ? options[selectedIndex] : undefined;

  const optionId = useCallback(
    (index: number) => `${baseId}-option-${index}`,
    [baseId],
  );

  const clearTypeahead = useCallback(() => {
    if (typeaheadRef.current.timer !== null) {
      window.clearTimeout(typeaheadRef.current.timer);
      typeaheadRef.current.timer = null;
    }
    typeaheadRef.current.buffer = "";
  }, []);

  useEffect(() => clearTypeahead, [clearTypeahead]);

  useEffect(() => {
    if (disabled && open) {
      setOpen(false);
    }
  }, [disabled, open]);

  const computePosition = useCallback((): MenuPosition | null => {
    const trigger = triggerRef.current;
    if (!trigger) return null;

    const rect = trigger.getBoundingClientRect();
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    const listEl = listRef.current;

    const minWidth =
      variant === "compact" ? Math.max(rect.width, 168) : rect.width;
    const measuredWidth = listEl ? listEl.offsetWidth : 0;
    const menuWidth = Math.max(minWidth, measuredWidth);
    const desiredHeight = Math.min(
      listEl?.scrollHeight || options.length * 40 + 8,
      MAX_MENU_HEIGHT,
    );

    const spaceBelow = Math.max(0, vh - rect.bottom - VIEWPORT_MARGIN - MENU_GAP);
    const spaceAbove = Math.max(0, rect.top - VIEWPORT_MARGIN - MENU_GAP);
    const placement: "down" | "up" =
      spaceBelow >= desiredHeight || spaceBelow >= spaceAbove ? "down" : "up";

    const availableVertical = placement === "down" ? spaceBelow : spaceAbove;
    const maxHeight = Math.min(
      MAX_MENU_HEIGHT,
      Math.max(96, availableVertical),
    );

    let left = align === "end" ? rect.right - menuWidth : rect.left;
    left = Math.min(left, vw - menuWidth - VIEWPORT_MARGIN);
    left = Math.max(VIEWPORT_MARGIN, left);

    if (placement === "up") {
      return {
        bottom: vh - rect.top + MENU_GAP,
        left,
        minWidth,
        maxHeight,
        placement,
      };
    }

    return {
      top: rect.bottom + MENU_GAP,
      left,
      minWidth,
      maxHeight,
      placement,
    };
  }, [align, options.length, variant]);

  useIsomorphicLayoutEffect(() => {
    if (!open) {
      setPosition(null);
      return;
    }
    const update = () => {
      const next = computePosition();
      if (next) setPosition(next);
    };
    update();
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    return () => {
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
    };
  }, [open, computePosition]);

  // Animate entrance once when positioned; honours prefers-reduced-motion inside animatePopoverIn.
  const hasPosition = position !== null;
  const placementRef = useRef<"down" | "up">("down");
  if (position) {
    placementRef.current = position.placement;
  }
  useEffect(() => {
    if (!open || !hasPosition) return;
    return animatePopoverIn(listRef.current, placementRef.current);
  }, [open, hasPosition]);

  // Keep the active option scrolled into view when navigating by keyboard.
  useEffect(() => {
    if (!open || activeIndex < 0) return;
    optionRefs.current[activeIndex]?.scrollIntoView?.({ block: "nearest" });
  }, [open, activeIndex]);

  const closeMenu = useCallback(
    (restoreFocus: boolean) => {
      setOpen(false);
      clearTypeahead();
      if (restoreFocus) {
        triggerRef.current?.focus();
      }
    },
    [clearTypeahead],
  );

  // Dismiss on outside click/tap or Escape anywhere on the document.
  useEffect(() => {
    if (!open) return;

    function handlePointer(e: MouseEvent | TouchEvent) {
      const target = e.target as Node | null;
      if (!target) return;
      if (
        triggerRef.current?.contains(target) ||
        listRef.current?.contains(target)
      ) {
        return;
      }
      closeMenu(false);
    }

    function handleDocumentKeyDown(e: globalThis.KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        closeMenu(true);
      }
    }

    document.addEventListener("mousedown", handlePointer);
    document.addEventListener("touchstart", handlePointer);
    document.addEventListener("keydown", handleDocumentKeyDown, true);
    return () => {
      document.removeEventListener("mousedown", handlePointer);
      document.removeEventListener("touchstart", handlePointer);
      document.removeEventListener("keydown", handleDocumentKeyDown, true);
    };
  }, [open, closeMenu]);

  const openWithIndex = useCallback(
    (preferredIndex: number) => {
      if (disabled) return;
      const fallback = findFirstEnabledIndex(options);
      const nextIndex =
        preferredIndex >= 0 && !options[preferredIndex]?.disabled
          ? preferredIndex
          : fallback;
      setActiveIndex(nextIndex);
      setOpen(true);
    },
    [disabled, options],
  );

  const commitSelection = useCallback(
    (index: number) => {
      const opt = options[index];
      if (!opt || opt.disabled) return;
      if (opt.value !== value) {
        onChange(opt.value);
      }
      closeMenu(true);
    },
    [closeMenu, onChange, options, value],
  );

  const handleTypeahead = useCallback(
    (char: string) => {
      const state = typeaheadRef.current;
      if (state.timer !== null) {
        window.clearTimeout(state.timer);
      }

      const sameSingleChar =
        state.buffer.length === 1 &&
        normalizeForSearch(state.buffer) === normalizeForSearch(char);

      const nextQuery = sameSingleChar ? char : state.buffer + char;
      const startIndex = sameSingleChar
        ? (activeIndex >= 0 ? activeIndex + 1 : 0)
        : open && activeIndex >= 0
          ? activeIndex
          : selectedIndex >= 0
            ? selectedIndex
            : 0;

      let match = findTypeaheadMatch(options, nextQuery, startIndex);
      if (match === -1 && nextQuery.length > 1) {
        match = findTypeaheadMatch(
          options,
          char,
          activeIndex >= 0 ? activeIndex + 1 : 0,
        );
        state.buffer = char;
      } else {
        state.buffer = nextQuery;
      }

      state.timer = window.setTimeout(() => {
        state.buffer = "";
        state.timer = null;
      }, TYPEAHEAD_RESET_MS);

      if (match >= 0) {
        if (!open) {
          setOpen(true);
        }
        setActiveIndex(match);
      }
    },
    [activeIndex, open, options, selectedIndex],
  );

  function handleTriggerClick() {
    if (disabled) return;
    if (open) {
      closeMenu(false);
    } else {
      openWithIndex(selectedIndex);
    }
  }

  function handleKeyDown(e: KeyboardEvent<HTMLButtonElement>) {
    if (disabled) return;

    const isPrintable =
      e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey;

    if (!open) {
      if (e.key === "ArrowDown" || e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        openWithIndex(selectedIndex);
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        openWithIndex(
          selectedIndex >= 0 ? selectedIndex : findLastEnabledIndex(options),
        );
        return;
      }
      if (e.key === "Home") {
        e.preventDefault();
        openWithIndex(findFirstEnabledIndex(options));
        return;
      }
      if (e.key === "End") {
        e.preventDefault();
        openWithIndex(findLastEnabledIndex(options));
        return;
      }
      if (isPrintable) {
        e.preventDefault();
        handleTypeahead(e.key);
      }
      return;
    }

    switch (e.key) {
      case "ArrowDown":
        e.preventDefault();
        setActiveIndex((curr) =>
          curr < 0
            ? findFirstEnabledIndex(options)
            : findNextEnabledIndex(options, curr, 1),
        );
        break;
      case "ArrowUp":
        e.preventDefault();
        if (e.altKey && activeIndex >= 0) {
          commitSelection(activeIndex);
        } else {
          setActiveIndex((curr) =>
            curr < 0
              ? findLastEnabledIndex(options)
              : findNextEnabledIndex(options, curr, -1),
          );
        }
        break;
      case "Home":
        e.preventDefault();
        setActiveIndex(findFirstEnabledIndex(options));
        break;
      case "End":
        e.preventDefault();
        setActiveIndex(findLastEnabledIndex(options));
        break;
      case "PageDown":
        e.preventDefault();
        setActiveIndex((curr) =>
          curr < 0
            ? findFirstEnabledIndex(options)
            : findNextEnabledIndex(options, curr, PAGE_STEP),
        );
        break;
      case "PageUp":
        e.preventDefault();
        setActiveIndex((curr) =>
          curr < 0
            ? findLastEnabledIndex(options)
            : findNextEnabledIndex(options, curr, -PAGE_STEP),
        );
        break;
      case "Enter":
        e.preventDefault();
        if (activeIndex >= 0) {
          commitSelection(activeIndex);
        } else {
          closeMenu(true);
        }
        break;
      case " ":
        e.preventDefault();
        if (typeaheadRef.current.buffer.length > 0) {
          handleTypeahead(" ");
        } else if (activeIndex >= 0) {
          commitSelection(activeIndex);
        } else {
          closeMenu(true);
        }
        break;
      case "Escape":
        e.preventDefault();
        e.stopPropagation();
        closeMenu(true);
        break;
      case "Tab":
        closeMenu(false);
        break;
      default:
        if (isPrintable) {
          e.preventDefault();
          handleTypeahead(e.key);
        }
        break;
    }
  }

  const activeOptionId =
    open && activeIndex >= 0 && options[activeIndex]
      ? optionId(activeIndex)
      : undefined;

  const portalTarget =
    open && typeof document !== "undefined"
      ? (triggerRef.current?.closest("dialog") ?? document.body)
      : null;

  const triggerClasses =
    variant === "compact"
      ? cn(
          "glass-card inline-flex h-10 cursor-pointer items-center justify-between gap-2 rounded-control border border-glass px-2.5 text-sm text-fg-muted transition-colors motion-reduce:transition-none",
          "hover:bg-hover-glass hover:text-fg",
          "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon",
          "disabled:cursor-not-allowed disabled:opacity-50",
          open && "border-neon bg-hover-glass text-fg",
          className,
        )
      : cn(
          "glass-field flex cursor-pointer items-center justify-between gap-2 rounded-control border border-glass bg-field text-left text-fg",
          "disabled:cursor-not-allowed disabled:opacity-50",
          "aria-[invalid=true]:border-danger aria-[invalid=true]:shadow-none",
          size === "sm"
            ? "h-9 px-2.5 text-xs sm:text-sm"
            : "h-11 w-full px-3 text-sm",
          open && "border-neon shadow-[0_0_0_3px_var(--neon-halo-far)]",
          className,
        );

  return (
    <>
      <button
        ref={triggerRef}
        id={id}
        type="button"
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listboxId}
        aria-activedescendant={activeOptionId}
        aria-label={ariaLabel}
        aria-labelledby={ariaLabelledBy}
        aria-describedby={ariaDescribedBy}
        aria-invalid={ariaInvalid}
        disabled={disabled}
        onClick={handleTriggerClick}
        onKeyDown={handleKeyDown}
        className={triggerClasses}
      >
        <span className="flex min-w-0 items-center gap-1.5">
          {leadingIcon}
          <span
            lang={selectedOption?.lang}
            className={cn(
              "truncate",
              !selectedOption && "text-fg-muted",
            )}
          >
            {selectedOption?.label ?? placeholder ?? ""}
          </span>
        </span>
        <ChevronDown
          className={cn(
            "h-4 w-4 shrink-0 text-fg-muted transition-transform duration-150 motion-reduce:transition-none",
            open && "rotate-180 text-lit",
          )}
          aria-hidden
        />
      </button>

      {name ? <input type="hidden" name={name} value={value} /> : null}

      {open && portalTarget
        ? createPortal(
            <ul
              ref={listRef}
              id={listboxId}
              role="listbox"
              aria-label={ariaLabel}
              aria-labelledby={ariaLabelledBy}
              tabIndex={-1}
              onMouseDown={(e) => e.preventDefault()}
              style={
                position
                  ? {
                      top: position.top,
                      bottom: position.bottom,
                      left: position.left,
                      minWidth: position.minWidth,
                      maxHeight: position.maxHeight,
                    }
                  : { visibility: "hidden", top: 0, left: 0 }
              }
              className={cn(
                "glass-dialog fixed z-[60] overflow-y-auto rounded-control border border-glass p-1 shadow-menu focus:outline-none",
                listClassName,
              )}
            >
              {options.map((option, index) => {
                const isSelected = option.value === value;
                const isActive = index === activeIndex;
                return (
                  <li
                    key={option.value}
                    ref={(el) => {
                      optionRefs.current[index] = el;
                    }}
                    id={optionId(index)}
                    role="option"
                    aria-selected={isSelected}
                    aria-disabled={option.disabled || undefined}
                    lang={option.lang}
                    data-active={isActive ? "true" : undefined}
                    data-selected={isSelected ? "true" : undefined}
                    onMouseMove={() => {
                      if (!option.disabled && activeIndex !== index) {
                        setActiveIndex(index);
                      }
                    }}
                    onClick={() => commitSelection(index)}
                    className={cn(
                      "flex cursor-pointer select-none items-center justify-between gap-2 rounded-md px-2.5 py-2 text-sm transition-colors motion-reduce:transition-none",
                      option.disabled
                        ? "cursor-not-allowed text-fg-muted opacity-50"
                        : isActive
                          ? cn(
                              "bg-focused text-lit ring-1 ring-inset ring-neon",
                              isSelected && "font-medium",
                            )
                          : isSelected
                            ? "font-medium text-lit hover:bg-hover-glass"
                            : "text-fg hover:bg-hover-glass",
                    )}
                  >
                    <span className="truncate">{option.label}</span>
                    {isSelected ? (
                      <Check
                        className="h-4 w-4 shrink-0 text-neon"
                        aria-hidden
                      />
                    ) : null}
                  </li>
                );
              })}
            </ul>,
            portalTarget,
          )
        : null}
    </>
  );
}
