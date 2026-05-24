"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

import { cn } from "@/lib/utils";

const ORDER = ["light", "dark", "system"] as const;
const ICON = { light: Sun, dark: Moon, system: Monitor };
const LABEL = { light: "Claro", dark: "Oscuro", system: "Sistema" };

/** Cycle light → dark → system. Avoids hydration mismatch by waiting for mount. */
export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const current = (mounted ? (theme ?? "system") : "system") as
    | "light"
    | "dark"
    | "system";
  const Icon = ICON[current];

  function cycle() {
    const next = ORDER[(ORDER.indexOf(current) + 1) % ORDER.length];
    setTheme(next);
  }

  return (
    <button
      type="button"
      onClick={cycle}
      aria-label={`Tema: ${LABEL[current]}`}
      title={`Tema: ${LABEL[current]}`}
      className={cn(
        "inline-flex h-9 w-9 items-center justify-center rounded-md text-fg-muted",
        "hover:bg-surface-2 hover:text-fg",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-bg",
      )}
    >
      <Icon className="h-5 w-5" aria-hidden />
    </button>
  );
}
