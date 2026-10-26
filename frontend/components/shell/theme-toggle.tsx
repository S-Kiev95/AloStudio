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
        "relative inline-flex h-10 w-10 items-center justify-center rounded-control text-fg-muted transition-colors",
        "after:absolute after:-inset-0.5 after:content-['']",
        "hover:bg-hover-glass hover:text-fg",
        "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon",
      )}
    >
      <Icon className="h-5 w-5" aria-hidden />
    </button>
  );
}
