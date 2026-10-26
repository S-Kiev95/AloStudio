"use client";

import { Trash2 } from "lucide-react";

import { Input } from "@/components/ui/input";
import { selectClassName } from "@/components/ui/select";
import {
  AUTOMATION_ACTIONS,
  type AutomationActionName,
} from "@/lib/api/automation-rules";
import { cn } from "@/lib/utils";

import { ACTION_META } from "../shared/action-meta";

export function AutomationActionRow({
  value,
  onChange,
  onRemove,
}: {
  value: { action_name: AutomationActionName; text: string };
  onChange: (next: {
    action_name: AutomationActionName;
    text: string;
  }) => void;
  onRemove: () => void;
}) {
  const meta = ACTION_META[value.action_name];

  return (
    <div className="flex flex-wrap items-start gap-2 rounded-md border border-glass bg-surface-2/40 p-2">
      <select
        aria-label="Acción"
        value={value.action_name}
        onChange={(e) =>
          onChange({
            action_name: e.target.value as AutomationActionName,
            text: "",
          })
        }
        className={selectClassName("sm")}
      >
        {AUTOMATION_ACTIONS.map((a) => (
          <option key={a} value={a}>
            {ACTION_META[a]?.label ?? a}
          </option>
        ))}
      </select>

      {meta?.kind === "none" ? (
        <p className="self-center text-xs text-fg-muted">Sin parámetros</p>
      ) : meta?.kind === "enum" ? (
        <select
          aria-label="Valor"
          value={value.text || (meta.options?.[0] ?? "")}
          onChange={(e) => onChange({ ...value, text: e.target.value })}
          className={cn(selectClassName("sm"), "min-w-32 flex-1")}
        >
          {meta.options?.map((opt) => (
            <option key={opt} value={opt}>
              {opt}
            </option>
          ))}
        </select>
      ) : (
        <Input
          aria-label="Parámetros"
          value={value.text}
          onChange={(e) => onChange({ ...value, text: e.target.value })}
          placeholder={meta?.placeholder}
          className="h-9 min-w-44 flex-1"
        />
      )}

      <button
        type="button"
        aria-label="Quitar acción"
        title="Quitar acción"
        onClick={onRemove}
        className="rounded-md p-2 text-fg-muted hover:bg-hover-glass hover:text-danger focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Trash2 className="h-4 w-4" aria-hidden />
      </button>
    </div>
  );
}
