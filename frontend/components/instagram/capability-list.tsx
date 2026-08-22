"use client";

import { AlertTriangle, Check, Minus } from "lucide-react";

import type { Capability } from "@/lib/inboxes/instagram-capabilities";

/**
 * What a connection method can do, as a list.
 *
 * Shared by the pre-connect dialog and the paste-a-token form so the two
 * can never drift into telling the admin different things about the same
 * flow.
 */
export function CapabilityList({
  capabilities,
  compact = false,
}: {
  capabilities: Capability[];
  compact?: boolean;
}) {
  return (
    <ul className={compact ? "space-y-1" : "space-y-2"}>
      {capabilities.map((cap) => (
        <CapabilityRow key={cap.label} capability={cap} compact={compact} />
      ))}
    </ul>
  );
}

function CapabilityRow({
  capability,
  compact,
}: {
  capability: Capability;
  compact: boolean;
}) {
  const { level, label, note } = capability;
  const size = compact ? "h-3.5 w-3.5" : "h-4 w-4";
  const icon =
    level === "yes" ? (
      <Check className={`mt-0.5 shrink-0 text-success ${size}`} aria-hidden />
    ) : level === "partial" ? (
      <AlertTriangle
        className={`mt-0.5 shrink-0 text-warning ${size}`}
        aria-hidden
      />
    ) : (
      <Minus className={`mt-0.5 shrink-0 text-danger ${size}`} aria-hidden />
    );
  // Screen readers get the verdict as a word — an icon alone says nothing.
  const estado = level === "yes" ? "Sí" : level === "partial" ? "Limitado" : "No";

  return (
    <li className={`flex gap-2 ${compact ? "text-xs" : "text-sm"}`}>
      {icon}
      <span className="min-w-0">
        <span className="sr-only">{estado}: </span>
        <span className={level === "no" ? "text-fg-muted" : undefined}>
          {label}
        </span>
        {note && !compact ? (
          <span className="mt-0.5 block text-xs text-fg-muted">{note}</span>
        ) : null}
      </span>
    </li>
  );
}
