"use client";

import { X } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { selectClassName } from "@/components/ui/select";
import type { FilterCondition, FilterOperator } from "@/lib/api/conversations";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n/provider";
import type { MessageKey } from "@/lib/i18n/translate";

type ValueKind = "text" | "date" | "bool";

type AttrDef = {
  key: string;
  label: MessageKey;
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
  { key: "name", label: "contacts.filters.attr.name", ops: TEXT_OPS, value: "text" },
  { key: "email", label: "contacts.filters.attr.email", ops: TEXT_OPS, value: "text" },
  { key: "phone_number", label: "contacts.filters.attr.phone", ops: TEXT_OPS, value: "text" },
  { key: "identifier", label: "contacts.filters.attr.identifier", ops: TEXT_OPS, value: "text" },
  { key: "company_name", label: "contacts.filters.attr.company", ops: TEXT_OPS, value: "text" },
  { key: "blocked", label: "contacts.filters.attr.blocked", ops: BOOL_OPS, value: "bool" },
  { key: "created_at", label: "contacts.filters.attr.created", ops: DATE_OPS, value: "date" },
];

const OP_LABELS: Record<FilterOperator, MessageKey> = {
  equal_to: "conversations.filters.op.equal_to",
  not_equal_to: "conversations.filters.op.not_equal_to",
  contains: "conversations.filters.op.contains",
  does_not_contain: "conversations.filters.op.does_not_contain",
  starts_with: "conversations.filters.op.starts_with",
  is_present: "conversations.filters.op.is_present",
  is_not_present: "conversations.filters.op.is_not_present",
  is_greater_than: "conversations.filters.op.is_greater_than",
  is_less_than: "conversations.filters.op.is_less_than",
};

const SELECT_CLS = selectClassName("sm");

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
  const t = useT();
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
    <div className="mb-3 space-y-3 rounded-md border border-glass bg-surface-2 p-3">
      {rows.map((row, i) => {
        const def = attrDef(row.attribute_key);
        return (
          <div key={i} className="flex flex-wrap items-center gap-2">
            <select
              value={row.attribute_key}
              onChange={(e) => changeAttribute(i, e.target.value)}
              aria-label={t("conversations.filters.attribute")}
              className={SELECT_CLS}
            >
              {ATTRIBUTES.map((a) => (
                <option key={a.key} value={a.key}>
                  {t(a.label)}
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
              aria-label={t("conversations.filters.operator")}
              className={SELECT_CLS}
            >
              {def.ops.map((op) => (
                <option key={op} value={op}>
                  {t(OP_LABELS[op])}
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
              aria-label={t("conversations.filters.removeCondition")}
              className="ml-auto rounded-md p-1 text-fg-muted hover:bg-hover-glass hover:text-fg disabled:opacity-40"
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
          className="rounded-control border border-glass bg-field px-3 py-1.5 text-sm font-medium text-fg hover:bg-hover-glass"
        >
          {t("conversations.filters.addCondition")}
        </button>
        {rows.length > 1 ? (
          <div className="flex items-center gap-1 text-xs text-fg-muted">
            <span>{t("conversations.filters.match")}</span>
            <button
              type="button"
              onClick={() => setMatch("AND")}
              aria-pressed={match === "AND"}
              className={matchCls(match === "AND")}
            >
              {t("conversations.filters.matchAll")}
            </button>
            <button
              type="button"
              onClick={() => setMatch("OR")}
              aria-pressed={match === "OR"}
              className={matchCls(match === "OR")}
            >
              {t("conversations.filters.matchAny")}
            </button>
          </div>
        ) : null}
      </div>

      <div className="flex items-center gap-2 border-t border-glass pt-3">
        <Button type="button" size="sm" onClick={apply}>
          {t("actions.apply")}
        </Button>
        <Button type="button" size="sm" variant="secondary" onClick={onCancel}>
          {t("actions.cancel")}
        </Button>
        {initial.length > 0 ? (
          <button
            type="button"
            onClick={onClear}
            className="ml-auto rounded-md px-3 py-1.5 text-sm font-medium text-fg-muted hover:text-fg"
          >
            {t("conversations.filters.clear")}
          </button>
        ) : null}
      </div>

      <div className="flex flex-wrap items-center gap-2 border-t border-glass pt-3">
        <input
          type="text"
          value={saveName}
          onChange={(e) => setSaveName(e.target.value)}
          placeholder={t("contacts.filters.saveAsSegment")}
          aria-label={t("contacts.filters.segmentName")}
          className={cn(SELECT_CLS, "min-w-[10rem] flex-1")}
        />
        <Button
          type="button"
          size="sm"
          variant="secondary"
          onClick={save}
          disabled={!saveName.trim() || buildConditions().length === 0}
        >
          {t("contacts.filters.saveSegment")}
        </Button>
      </div>
    </div>
  );
}

function matchCls(active: boolean) {
  return cn(
    "rounded-sm px-2 py-0.5 font-medium",
    active ? "bg-focused text-lit" : "text-fg-muted hover:text-fg",
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
  const t = useT();
  if (def.value === "bool") {
    return (
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label={t("conversations.filters.value")}
        className={SELECT_CLS}
      >
        <option value="">{t("actions.selectPlaceholder")}</option>
        <option value="true">{t("actions.yes")}</option>
        <option value="false">{t("actions.no")}</option>
      </select>
    );
  }
  return (
    <Input
      type={def.value === "date" ? "date" : "text"}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      aria-label={t("conversations.filters.value")}
      className="h-9 w-auto"
    />
  );
}
