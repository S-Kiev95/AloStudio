"use client";

import {
  createContext,
  useContext,
  useEffect,
  type ReactNode,
} from "react";

import { cn } from "@/lib/utils";

type PageSignContextValue = {
  setSignTitle: (title: string | null) => void;
};

export const PageSignContext = createContext<PageSignContextValue | null>(null);

export interface PageHeaderProps {
  /** Page title. Rendered as the topbar neon sign inside DashboardShell, or inline when standalone. */
  title: string;
  /** Optional explicit topbar sign when `title` is a separate body greeting (e.g. "Inicio" + "Buenas noches"). */
  signTitle?: string;
  description?: ReactNode;
  actions?: ReactNode;
  className?: string;
}

/**
 * Shared page header (PLAN.design-neon §3).
 * Inside DashboardShell, promotes the section title into the topbar `.neon-sign`
 * so the page sign appears once at the top-left of the work panel and renders
 * optional description + actions cleanly below. Outside DashboardShell (unit
 * tests, standalone routes), renders the `.neon-sign` `<h1>` directly.
 */
export function PageHeader({
  title,
  signTitle,
  description,
  actions,
  className,
}: PageHeaderProps) {
  const shell = useContext(PageSignContext);
  const effectiveSign = signTitle ?? title;

  useEffect(() => {
    if (!shell) return;
    shell.setSignTitle(effectiveSign);
    return () => shell.setSignTitle(null);
  }, [shell, effectiveSign]);

  if (!shell) {
    return (
      <div
        className={cn(
          "flex flex-wrap items-center justify-between gap-3",
          className,
        )}
      >
        <div className="min-w-0">
          <div className="neon-sign">
            <h1 className="text-[24px] leading-[1.2] lg:text-[34px]">{title}</h1>
          </div>
          {description ? (
            <p className="mt-1 text-sm text-fg-muted">{description}</p>
          ) : null}
        </div>
        {actions ? (
          <div className="flex flex-wrap items-center gap-2">{actions}</div>
        ) : null}
      </div>
    );
  }

  const hasSeparateBodyHeading = Boolean(signTitle && signTitle !== title);
  if (!hasSeparateBodyHeading && !description && !actions) {
    return null;
  }

  return (
    <div
      className={cn(
        "flex flex-wrap items-center justify-between gap-3",
        className,
      )}
    >
      {hasSeparateBodyHeading || description ? (
        <div className="min-w-0">
          {hasSeparateBodyHeading ? (
            <h2 className="text-2xl font-medium text-fg sm:text-3xl">{title}</h2>
          ) : null}
          {description ? (
            <p
              className={cn(
                "text-sm text-fg-muted",
                hasSeparateBodyHeading && "mt-1",
              )}
            >
              {description}
            </p>
          ) : null}
        </div>
      ) : null}
      {actions ? (
        <div
          className={cn(
            "flex flex-wrap items-center gap-2",
            !hasSeparateBodyHeading && !description && "ml-auto",
          )}
        >
          {actions}
        </div>
      ) : null}
    </div>
  );
}
