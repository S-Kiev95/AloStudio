"use client";

import { Trash2 } from "lucide-react";

import { Input } from "@/components/ui/input";
import {
  FILTER_OPERATOR_LABELS,
  FILTER_OPERATORS,
  type FilterOperator,
  OPERATORS_WITHOUT_VALUES,
  STANDARD_ATTRIBUTES,
} from "@/lib/api/automation-rules";

/** Editor draft for a condition — same shape as the wire row, plus
 * ``valuesText`` (comma-separated string) so the input stays controlled. */
export type ConditionDraft = {
  attribute_key: string;
  filter_operator: FilterOperator;
  query_operator: "AND" | "OR" | "";
  valuesText: string;
  custom_attribute_type?: string | null;
};

export function ConditionRow({
  index,
  total,
  value,
  onChange,
  onRemove,
}: {
  index: number;
  total: number;
  value: ConditionDraft;
  onChange: (next: ConditionDraft) => void;
  onRemove: () => void;
}) {
  const hideValues = OPERATORS_WITHOUT_VALUES.has(value.filter_operator);
  const isLast = index === total - 1;

  return (
    <div className="space-y-2 rounded-md border border-border bg-surface p-2">
      <div className="flex flex-wrap items-start gap-2">
        <select
          aria-label="Atributo"
          value={value.attribute_key}
          onChange={(e) =>
            onChange({ ...value, attribute_key: e.target.value })
          }
          className="h-9 rounded-md border border-border bg-surface px-2 text-sm text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {STANDARD_ATTRIBUTES.map((a) => (
            <option key={a.key} value={a.key}>
              {a.label}
            </option>
          ))}
        </select>

        <select
          aria-label="Operador"
          value={value.filter_operator}
          onChange={(e) =>
            onChange({
              ...value,
              filter_operator: e.target.value as FilterOperator,
            })
          }
          className="h-9 rounded-md border border-border bg-surface px-2 text-sm text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {FILTER_OPERATORS.map((op) => (
            <option key={op} value={op}>
              {FILTER_OPERATOR_LABELS[op]}
            </option>
          ))}
        </select>

        {!hideValues ? (
          <Input
            aria-label="Valores"
            value={value.valuesText}
            onChange={(e) =>
              onChange({ ...value, valuesText: e.target.value })
            }
            placeholder="valor (o varios separados por coma)"
            className="h-9 min-w-44 flex-1"
          />
        ) : (
          <p className="self-center text-xs text-fg-muted">Sin valor</p>
        )}

        <button
          type="button"
          aria-label="Quitar condición"
          title="Quitar condición"
          onClick={onRemove}
          className="rounded-md p-2 text-fg-muted hover:bg-surface-2 hover:text-danger focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Trash2 className="h-4 w-4" aria-hidden />
        </button>
      </div>

      {!isLast ? (
        <div className="flex gap-3 pl-1 text-sm">
          <label className="flex items-center gap-1.5 text-fg-muted">
            <input
              type="radio"
              checked={value.query_operator === "AND"}
              onChange={() => onChange({ ...value, query_operator: "AND" })}
            />
            Y (todas)
          </label>
          <label className="flex items-center gap-1.5 text-fg-muted">
            <input
              type="radio"
              checked={value.query_operator === "OR"}
              onChange={() => onChange({ ...value, query_operator: "OR" })}
            />
            O (cualquiera)
          </label>
        </div>
      ) : null}
    </div>
  );
}

/** Comma-split values from the editor into the wire ``values`` array. */
export function valuesFromText(text: string): string[] {
  return text
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

/** Inverse — join the wire ``values`` array into the editor text. */
export function valuesToText(values: unknown[] | undefined): string {
  return (values ?? []).map(String).join(", ");
}
