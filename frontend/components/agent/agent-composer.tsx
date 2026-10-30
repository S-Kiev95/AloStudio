"use client";

import { ArrowUp } from "lucide-react";
import { useEffect, useRef } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

const MAX_CHARS = 4000;
const SHOW_COUNTER_FROM = 3500;
const MAX_TEXTAREA_HEIGHT_PX = 144; // ~6 lines

export function AgentComposer({
  value,
  onChange,
  onSubmit,
  disabled = false,
  isBusy = false,
  error,
}: {
  value: string;
  onChange: (next: string) => void;
  onSubmit: () => void;
  disabled?: boolean;
  isBusy?: boolean;
  error: string | null;
}) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    if (!value) {
      el.style.height = "";
      return;
    }
    el.style.height = "auto";
    if (el.scrollHeight > 0) {
      el.style.height = `${Math.min(el.scrollHeight, MAX_TEXTAREA_HEIGHT_PX)}px`;
    }
  }, [value]);

  const charCount = Array.from(value).length;
  const overLimit = charCount > MAX_CHARS;
  const canSend =
    !disabled && !isBusy && value.trim().length > 0 && !overLimit;

  return (
    <div className="shrink-0 border-t border-glass bg-surface p-3">
      {error ? (
        <p role="alert" className="mb-2 text-xs text-danger">
          {error}
        </p>
      ) : null}

      <div className="flex items-end gap-2">
        <Textarea
          ref={textareaRef}
          rows={1}
          value={value}
          disabled={disabled}
          aria-invalid={overLimit || undefined}
          aria-label="Mensaje para el agente"
          placeholder={
            disabled
              ? "El agente no está disponible"
              : "Escribí un mensaje…"
          }
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (
              e.key === "Enter" &&
              !e.shiftKey &&
              !e.nativeEvent.isComposing
            ) {
              e.preventDefault();
              if (canSend) {
                onSubmit();
              }
            }
          }}
          className="max-h-36 min-h-[44px] flex-1 overflow-y-auto py-2.5"
        />

        <Button
          type="button"
          size="icon"
          aria-label="Enviar mensaje"
          disabled={!canSend}
          onClick={onSubmit}
          className="h-11 w-11 shrink-0"
        >
          <ArrowUp className="h-4 w-4" aria-hidden />
        </Button>
      </div>

      {charCount >= SHOW_COUNTER_FROM ? (
        <div className="mt-1.5 flex justify-end">
          <span
            className={cn(
              "font-numeric text-xs tabular-nums",
              overLimit ? "font-medium text-danger" : "text-fg-muted",
            )}
          >
            {charCount}/{MAX_CHARS}
          </span>
        </div>
      ) : null}
    </div>
  );
}
