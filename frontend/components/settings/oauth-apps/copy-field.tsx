"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";

/** A labelled value with a copy button (same look as the inbox details). */
export function CopyField({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      // clipboard.writeText can throw in non-secure contexts — ignore.
    }
  }

  return (
    <div className="min-w-0 space-y-1">
      <p className="text-xs font-medium uppercase text-fg-muted">{label}</p>
      <div className="flex items-center gap-2">
        <code className="block min-w-0 flex-1 truncate rounded bg-surface-2 px-2 py-1 font-numeric text-xs text-fg">
          {value}
        </code>
        <button
          type="button"
          aria-label={`Copiar ${label}`}
          title="Copiar"
          onClick={() => void copy()}
          className="shrink-0 rounded-md p-1.5 text-fg-muted hover:bg-surface-2 hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {copied ? (
            <Check className="h-4 w-4 text-success" aria-hidden />
          ) : (
            <Copy className="h-4 w-4" aria-hidden />
          )}
        </button>
      </div>
    </div>
  );
}
