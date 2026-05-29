import { type LucideIcon } from "lucide-react";
import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * Branded panel for error / 404 / empty-state screens. Centred card with an
 * optional icon, message + a primary action. Shared so the look stays
 * consistent across `error.tsx` and `not-found.tsx` at every level.
 */
export function FallbackPanel({
  icon: Icon,
  title,
  description,
  primary,
  secondary,
}: {
  icon?: LucideIcon;
  title: string;
  description?: string;
  primary?: { label: string; href?: string; onClick?: () => void };
  secondary?: { label: string; href?: string; onClick?: () => void };
}) {
  return (
    <div className="mx-auto flex max-w-md flex-col items-center gap-4 p-6 text-center">
      {Icon ? (
        <span className="flex h-12 w-12 items-center justify-center rounded-full bg-surface-2 text-fg-muted">
          <Icon className="h-6 w-6" aria-hidden />
        </span>
      ) : null}
      <h1 className="text-xl font-semibold text-fg">{title}</h1>
      {description ? (
        <p className="text-sm text-fg-muted">{description}</p>
      ) : null}
      {primary || secondary ? (
        <div className="flex flex-wrap items-center justify-center gap-2">
          {primary ? <Action variant="primary" {...primary} /> : null}
          {secondary ? <Action variant="secondary" {...secondary} /> : null}
        </div>
      ) : null}
    </div>
  );
}

function Action({
  variant,
  label,
  href,
  onClick,
}: {
  variant: "primary" | "secondary";
  label: string;
  href?: string;
  onClick?: () => void;
}) {
  const className = cn(buttonVariants({ variant, size: "sm" }));
  if (href) {
    return (
      <Link href={href} className={className}>
        {label}
      </Link>
    );
  }
  return (
    <button type="button" onClick={onClick} className={className}>
      {label}
    </button>
  );
}
