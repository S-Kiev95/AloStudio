"use client";

import { X } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { FilterCondition, FilterOperator } from "@/lib/api/conversations";
import { cn } from "@/lib/utils";

type ValueKind = "text" | "date" | "bool";

type AttrDef = {
  key: string;
  label: string;
  ops: FilterOperator[];
  value: ValueKind;
};

const TEXT_OPS: FilterOperator[] = [
  "equal_to",
  "not_equal_to",
  "contains",
  "does_not_contain",
  "starts_with",
  "is_present",
  "is_not_present",
];
const DATE_OPS: FilterOperator[] = [
  "is_greater_than",
  "is_less_than",
  "equal_to",
];
const BOOL_OPS: FilterOperator[] = ["equal_to"];

const ATTRIBUTES: AttrDef[] = [
  { key: "name", label: "Nombre", ops: TEXT_OPS, value: "text" },
  { key: "email", label: "Email", ops: TEXT_OPS, value: "text" },
  { key: "phone_number", label: "Teléfono", ops: TEXT_OPS, value: "text" },
  { key: "identifier", label: "Identificador", ops: TEXT_OPS, value: "text" },
  { key: "company_name", label: "Empresa", ops: TEXT_OPS, value: "text" },
  { key: "blocked", label: "Bloqueado", ops: BOOL_OPS, value: "bool" },
  { key: "created_at", label: "Creado", ops: DATE_OPS, value: "date" },
];

const OP_LABELS: Record<FilterOperator, string> = {
  equal_to: "es",
  not_equal_to: "no es",
  contains: "contiene",
  does_not_contain: "no contiene",
  starts_with: "empieza con",
  is_present: "tiene valor",
  is_not_present: "sin valor",
  is_greater_than: "después de",
  is_less_than: "antes de",
};

const SELECT_CLS =
  "h-9 rounded-md border border-border bg-surface px-2 text-sm text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

const needsValue = (op: FilterOperator) =>
  op !== "is_present" && op !== "is_not_present";

type DraftRow = {
  attribute_key: string;
  filter_operator: FilterOperator;
  value: string;
};

function attrDef(key: string): AttrDef {
  return ATTRIBUTES.find((a) => a.key === key) ?? ATTRIBUTES[0];
}

const blankRow = (): DraftRow => ({
  attribute_key: "name",
  filter_operator: "contains",
  value: "",
});

function toDraft(c: FilterCondition): DraftRow {
  return {
    attribute_key: c.attribute_key,
    filter_operator: c.filter_operator,
    value: c.values[0] != null ? String(c.values[0]) : "",
  };
}

export function ContactFilters({
  initial,
  initialMatch,
  onApply,
  onClear,
  onCancel,
  onSaveSegment,
}: {
  initial: FilterCondition[];
  initialMatch: "AND" | "OR";
  onApply: (conditions: FilterCondition[], match: "AND" | "OR") => void;
  onClear: () => void;
  onCancel: () => void;
  onSaveSegment: (
    name: string,
    conditions: FilterCondition[],
    match: "AND" | "OR",
  ) => void;
}) {
  const [rows, setRows] = useState<DraftRow[]>(
    initial.length > 0 ? initial.map(toDraft) : [blankRow()],
  );
  const [match, setMatch] = useState<"AND" | "OR">(initialMatch);
  const [saveName, setSaveName] = useState("");

  function updateRow(i: number, patch: Partial<DraftRow>) {
    setRows((prev) => prev.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  }
  function changeAttribute(i: number, key: string) {
    const def = attrDef(key);
    updateRow(i, { attribute_key: key, filter_operator: def.ops[0], value: "" });
  }
  function removeRow(i: number) {
    setRows((prev) =>
      prev.length <= 1 ? prev : prev.filter((_, idx) => idx !== i),
    );
  }

  function buildConditions(): FilterCondition[] {
    const conds: FilterCondition[] = [];
    for (const r of rows) {
      const wantsValue = needsValue(r.filter_operator);
      if (wantsValue && !r.value) continue; // skip incomplete rows
      conds.push({
        attribute_key: r.attribute_key,
        filter_operator: r.filter_operator,
        values: wantsValue ? [r.value] : [],
        query_operator: match,
      });
    }
    return conds;
  }

  function apply() {
    const conds = buildConditions();
    if (conds.length === 0) {
      onClear();
      return;
    }
    onApply(conds, match);
  }

  function save() {
    const name = saveName.trim();
    const conds = buildConditions();
    if (!name || conds.length === 0) return;
    onSaveSegment(name, conds, match);
    setSaveName("");
  }

  return (
    <div className="mb-3 space-y-3 rounded-md border border-border bg-surface-2 p-3">
      {rows.map((row, i) => {
        const def = attrDef(row.attribute_key);
        return (
          <div key={i} className="flex flex-wrap items-center gap-2">
            <select
              value={row.attribute_key}
              onChange={(e) => changeAttribute(i, e.target.value)}
              aria-label="Atributo"
              className={SELECT_CLS}
            >
              {ATTRIBUTES.map((a) => (
                <option key={a.key} value={a.key}>
                  {a.label}
                </option>
              ))}
            </select>
            <select
              value={row.filter_operator}
              onChange={(e) =>
                updateRow(i, {
                  filter_operator: e.target.value as FilterOperator,
                })
              }
              aria-label="Operador"
              className={SELECT_CLS}
            >
              {def.ops.map((op) => (
                <option key={op} value={op}>
                  {OP_LABELS[op]}
                </option>
              ))}
            </select>
            {needsValue(row.filter_operator) ? (
              <ValueControl
                def={def}
                value={row.value}
                onChange={(v) => updateRow(i, { value: v })}
              />
            ) : null}
            <button
              type="button"
              onClick={() => removeRow(i)}
              disabled={rows.length <= 1}
              aria-label="Quitar condición"
              className="ml-auto rounded-md p-1 text-fg-muted hover:bg-surface hover:text-fg disabled:opacity-40"
            >
              <X className="h-4 w-4" aria-hidden />
            </button>
          </div>
        );
      })}

      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => setRows((prev) => [...prev, blankRow()])}
          className="rounded-md border border-border bg-surface px-3 py-1.5 text-sm font-medium text-fg hover:bg-surface-2"
        >
          + Agregar condición
        </button>
        {rows.length > 1 ? (
          <div className="flex items-center gap-1 text-xs text-fg-muted">
            <span>Coincidir:</span>
            <button
              type="button"
              onClick={() => setMatch("AND")}
              aria-pressed={match === "AND"}
              className={matchCls(match === "AND")}
            >
              Todas
            </button>
            <button
              type="button"
              onClick={() => setMatch("OR")}
              aria-pressed={match === "OR"}
              className={matchCls(match === "OR")}
            >
              Cualquiera
            </button>
          </div>
        ) : null}
      </div>

      <div className="flex items-center gap-2 border-t border-border pt-3">
        <Button type="button" size="sm" onClick={apply}>
          Aplicar
        </Button>
        <Button type="button" size="sm" variant="secondary" onClick={onCancel}>
          Cancelar
        </Button>
        {initial.length > 0 ? (
          <button
            type="button"
            onClick={onClear}
            className="ml-auto rounded-md px-3 py-1.5 text-sm font-medium text-fg-muted hover:text-fg"
          >
            Limpiar filtros
          </button>
        ) : null}
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3">
        <input
          type="text"
          value={saveName}
          onChange={(e) => setSaveName(e.target.value)}
          placeholder="Guardar como segmento…"
          aria-label="Nombre del segmento"
          className={cn(SELECT_CLS, "min-w-[10rem] flex-1")}
        />
        <Button
          type="button"
          size="sm"
          variant="secondary"
          onClick={save}
          disabled={!saveName.trim() || buildConditions().length === 0}
        >
          Guardar segmento
        </Button>
      </div>
    </div>
  );
}

function matchCls(active: boolean) {
  return cn(
    "rounded px-2 py-0.5 font-medium",
    active ? "bg-surface text-fg" : "text-fg-muted hover:text-fg",
  );
}

function ValueControl({
  def,
  value,
  onChange,
}: {
  def: AttrDef;
  value: string;
  onChange: (v: string) => void;
}) {
  if (def.value === "bool") {
    return (
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label="Valor"
        className={SELECT_CLS}
      >
        <option value="">Seleccionar…</option>
        <option value="true">Sí</option>
        <option value="false">No</option>
      </select>
    );
  }
  return (
    <Input
      type={def.value === "date" ? "date" : "text"}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      aria-label="Valor"
      className="h-9 w-auto"
    />
  );
}
