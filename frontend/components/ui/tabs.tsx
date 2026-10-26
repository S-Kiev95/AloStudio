"use client";

import Link from "next/link";
import { createContext, useContext, type HTMLAttributes, type ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * Tabs — section tab rail (DESIGN.md §Tabs).
 * Tilt Neon 17px on a 1px Unlit Glass bottom rule, 4px apart, 10x14px padding;
 * the active tab carries Lit Text over a 2px glowing cobalt tube on the rail.
 */
export function tabItemClassName(active: boolean, className?: string) {
  return cn(
    "neon-tab inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap px-[14px] py-[10px] font-display text-[17px] font-normal leading-snug transition-colors",
    "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon",
    active ? "neon-tab-active text-lit" : "text-fg-muted hover:text-fg",
    className,
  );
}

type TabsContextValue = {
  value: string;
  onValueChange: (next: string) => void;
};

const TabsContext = createContext<TabsContextValue | null>(null);

export function Tabs({
  value,
  onValueChange,
  className,
  children,
}: {
  value: string;
  onValueChange: (next: string) => void;
  className?: string;
  children: ReactNode;
}) {
  return (
    <TabsContext.Provider value={{ value, onValueChange }}>
      <div className={className}>{children}</div>
    </TabsContext.Provider>
  );
}

export function TabsList({
  className,
  ...props
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      role="tablist"
      className={cn(
        "flex flex-wrap items-center gap-1 border-b border-glass",
        className,
      )}
      {...props}
    />
  );
}

export function TabsTrigger({
  value,
  className,
  children,
  disabled,
}: {
  value: string;
  className?: string;
  children: ReactNode;
  disabled?: boolean;
}) {
  const ctx = useContext(TabsContext);
  if (!ctx) {
    throw new Error("TabsTrigger must be used inside <Tabs>");
  }
  const active = ctx.value === value;
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      disabled={disabled}
      onClick={() => ctx.onValueChange(value)}
      className={cn(
        tabItemClassName(active),
        "disabled:pointer-events-none disabled:opacity-40",
        className,
      )}
    >
      {children}
    </button>
  );
}

export type NavTabItem = {
  href: string;
  label: ReactNode;
  active: boolean;
};

export function NavTabs({
  items,
  ariaLabel,
  className,
}: {
  items: NavTabItem[];
  ariaLabel?: string;
  className?: string;
}) {
  return (
    <nav
      aria-label={ariaLabel}
      className={cn(
        "flex flex-wrap items-center gap-1 border-b border-glass",
        className,
      )}
    >
      {items.map((item) => (
        <Link
          key={item.href}
          href={item.href}
          aria-current={item.active ? "page" : undefined}
          className={tabItemClassName(item.active)}
        >
          {item.label}
        </Link>
      ))}
    </nav>
  );
}
