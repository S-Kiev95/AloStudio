"use client";

import { X } from "lucide-react";
import { useState } from "react";

import { type Agent, type Label, useAgents, useLabels } from "@/lib/api/account";
import {
  type FilterCondition,
  type FilterOperator,
  type KnownAd,
  useKnownAds,
} from "@/lib/api/conversations";
import { type Inbox, useInboxes } from "@/lib/api/inboxes";
import { type Team, useTeams } from "@/lib/api/teams";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type ValueKind =
  | "status"
  | "priority"
  | "agent"
  | "inbox"
  | "team"
  | "label"
  | "ad";

type AttrDef = {
  key: string;
  label: string;
  ops: FilterOperator[];
  value: ValueKind;
};

const ALL_OPS: FilterOperator[] = [
  "equal_to",
  "not_equal_to",
  "is_present",
  "is_not_present",
];

const ATTRIBUTES: AttrDef[] = [
  { key: "status", label: "Estado", ops: ["equal_to", "not_equal_to"], value: "status" },
  { key: "priority", label: "Prioridad", ops: ALL_OPS, value: "priority" },
  { key: "assignee_id", label: "Asignado a", ops: ALL_OPS, value: "agent" },
  { key: "inbox_id", label: "Bandeja", ops: ALL_OPS, value: "inbox" },
  { key: "team_id", label: "Equipo", ops: ALL_OPS, value: "team" },
  { key: "labels", label: "Etiqueta", ops: ALL_OPS, value: "label" },
  // "tiene valor" answers "everything an ad brought in", which is the
  // question asked most often; equal_to narrows to one campaign.
  { key: "ad_id", label: "Anuncio", ops: ALL_OPS, value: "ad" },
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

const STATUS_OPTS = [
  { v: "open", l: "Abierta" },
  { v: "pending", l: "Pendiente" },
  { v: "resolved", l: "Resuelta" },
  { v: "snoozed", l: "Pospuesta" },
];
const PRIORITY_OPTS = [
  { v: "low", l: "Baja" },
  { v: "medium", l: "Media" },
  { v: "high", l: "Alta" },
  { v: "urgent", l: "Urgente" },
];

const SELECT_CLS =
  "h-9 rounded-md border border-border bg-surface px-2 text-sm text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

const needsValue = (op: FilterOperator) =>
  op === "equal_to" || op === "not_equal_to";

type DraftRow = {
  attribute_key: string;
  filter_operator: FilterOperator;
  value: string;
};

function attrDef(key: string): AttrDef {
  return ATTRIBUTES.find((a) => a.key === key) ?? ATTRIBUTES[0];
}

function toDraft(c: FilterCondition): DraftRow {
  return {
    attribute_key: c.attribute_key,
    filter_operator: c.filter_operator,
    value: c.values[0] != null ? String(c.values[0]) : "",
  };
}

const blankRow = (): DraftRow => ({
  attribute_key: "status",
  filter_operator: "equal_to",
  value: "",
});

export function ConversationFilters({
  accountId,
  initial,
  initialMatch,
  onApply,
  onClear,
  onCancel,
  onSaveView,
}: {
  accountId: string;
  initial: FilterCondition[];
  initialMatch: "AND" | "OR";
  onApply: (conditions: FilterCondition[], match: "AND" | "OR") => void;
  onClear: () => void;
  onCancel: () => void;
  onSaveView: (
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

  const agents = useAgents(accountId);
  const inboxes = useInboxes(accountId);
  const teams = useTeams(accountId);
  const ads = useKnownAds(accountId);
  const labels = useLabels(accountId);

  function updateRow(i: number, patch: Partial<DraftRow>) {
    setRows((prev) => prev.map((r, idx) => (idx === i ? { ...r, ...patch } : r)));
  }
  function changeAttribute(i: number, key: string) {
    const def = attrDef(key);
    updateRow(i, { attribute_key: key, filter_operator: def.ops[0], value: "" });
  }
  function removeRow(i: number) {
    setRows((prev) => (prev.length <= 1 ? prev : prev.filter((_, idx) => idx !== i)));
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
    onSaveView(name, conds, match);
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
                agents={agents.data ?? []}
                inboxes={inboxes.data ?? []}
                teams={teams.data ?? []}
                labels={labels.data ?? []}
                ads={ads.data ?? []}
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
          placeholder="Guardar como vista…"
          aria-label="Nombre de la vista"
          className={cn(SELECT_CLS, "min-w-[10rem] flex-1")}
        />
        <Button
          type="button"
          size="sm"
          variant="secondary"
          onClick={save}
          disabled={!saveName.trim() || buildConditions().length === 0}
        >
          Guardar vista
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
  agents,
  inboxes,
  teams,
  labels,
  ads,
}: {
  def: AttrDef;
  value: string;
  onChange: (v: string) => void;
  agents: Agent[];
  inboxes: Inbox[];
  teams: Team[];
  labels: Label[];
  ads: KnownAd[];
}) {
  let options: { v: string; l: string }[] = [];
  if (def.value === "status") options = STATUS_OPTS;
  else if (def.value === "priority") options = PRIORITY_OPTS;
  else if (def.value === "agent")
    options = agents.map((a) => ({ v: String(a.id), l: a.name }));
  else if (def.value === "inbox")
    options = inboxes.map((i) => ({ v: String(i.id), l: i.name }));
  else if (def.value === "team")
    options = teams.map((t) => ({ v: String(t.id), l: t.name }));
  else if (def.value === "label")
    options = labels.map((l) => ({ v: l.title, l: l.title }));
  else if (def.value === "ad")
    // Headline as the label — nobody recognises a Meta ad by its numeric id.
    options = ads.map((a) => ({ v: a.ad_id, l: a.headline }));

  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      aria-label="Valor"
      className={SELECT_CLS}
    >
      <option value="">Seleccionar…</option>
      {options.map((o) => (
        <option key={o.v} value={o.v}>
          {o.l}
        </option>
      ))}
    </select>
  );
}
