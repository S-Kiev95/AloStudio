"use client";

import { ArrowDown, ArrowUp, Plus, Trash2, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { selectClassName } from "@/components/ui/select";
import { type Pipeline, type StageKind, useUpdatePipeline } from "@/lib/api/crm";
import { useT } from "@/lib/i18n/provider";
import type { MessageKey } from "@/lib/i18n/translate";

import { stageLabel } from "./stage-label";

type Row = {
  key: string;
  id?: number;
  code: string | null;
  name: string;
  kind: StageKind;
  probability: string;
};

const KINDS: { value: StageKind; label: MessageKey }[] = [
  { value: "open", label: "opportunities.kinds.open" },
  { value: "won", label: "opportunities.kinds.won" },
  { value: "lost", label: "opportunities.kinds.lost" },
];

/** The stages of a pipeline: rename, reorder, add or drop them, and how
 *  many idle days make an open opportunity stale. */
export function PipelineDialog({
  accountId,
  pipeline,
  open,
  onClose,
}: {
  accountId: string;
  pipeline: Pipeline;
  open: boolean;
  onClose: () => void;
}) {
  const t = useT();
  const dialogRef = useRef<HTMLDialogElement>(null);
  const update = useUpdatePipeline(accountId);
  const [rows, setRows] = useState<Row[]>([]);
  const [rotten, setRotten] = useState("30");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const el = dialogRef.current;
    if (!el) return;
    if (open && !el.open) {
      if (typeof el.showModal === "function") el.showModal();
      else el.setAttribute("open", "");
    }
  }, [open]);

  useEffect(() => {
    if (!open) return;
    setError(null);
    setRotten(String(pipeline.rotten_days));
    setRows(
      pipeline.stages.map((s) => ({
        key: `s${s.id}`,
        id: s.id,
        code: s.code,
        name: s.name ?? "",
        kind: s.kind,
        probability: String(s.probability),
      })),
    );
  }, [open, pipeline]);

  function patch(index: number, change: Partial<Row>) {
    setRows((prev) => prev.map((r, i) => (i === index ? { ...r, ...change } : r)));
  }

  function move(index: number, by: number) {
    setRows((prev) => {
      const next = [...prev];
      const [row] = next.splice(index, 1);
      next.splice(index + by, 0, row);
      return next;
    });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    const days = Number(rotten);
    if (!Number.isInteger(days) || days < 1 || days > 365) {
      setError(t("opportunities.rottenInvalid"));
      return;
    }
    if (rows.some((r) => !r.code && !r.name.trim())) {
      setError(t("opportunities.stageNameRequired"));
      return;
    }
    if (!rows.some((r) => r.kind === "open")) {
      setError(t("opportunities.needOpenStage"));
      return;
    }
    try {
      await update.mutateAsync({
        id: pipeline.id,
        patch: {
          rotten_days: days,
          stages: rows.map((r) => ({
            id: r.id,
            name: r.name.trim() || null,
            kind: r.kind,
            probability: Math.min(100, Math.max(0, Math.round(Number(r.probability) || 0))),
          })),
        },
      });
      onClose();
    } catch (err) {
      setError((err as { message?: string })?.message ?? t("opportunities.saveFailed"));
    }
  }

  if (!open) return null;

  return (
    <dialog
      ref={dialogRef}
      onClose={onClose}
      aria-labelledby="pipeline-dialog-title"
      className="w-full max-w-2xl rounded-panel border border-glass bg-surface p-0 text-fg shadow-menu backdrop:bg-backdrop/75"
    >
      <form onSubmit={handleSubmit} className="space-y-4 p-5">
        <div className="flex items-start justify-between gap-3">
          <h2 id="pipeline-dialog-title" className="text-lg font-medium text-fg">
            {t("opportunities.editStages")}
          </h2>
          <button
            type="button"
            aria-label={t("actions.closeDialog")}
            onClick={onClose}
            className="inline-flex h-9 w-9 items-center justify-center rounded-md text-fg-muted hover:bg-hover-glass focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        </div>

        {error ? (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        ) : null}

        <ol className="space-y-2">
          {rows.map((row, index) => (
            <li key={row.key} className="grid grid-cols-[1fr_8rem_5rem_auto] items-center gap-2">
              <Input
                aria-label={t("opportunities.stageName", { n: index + 1 })}
                value={row.name}
                placeholder={row.code ? stageLabel(t, { name: null, code: row.code }) : ""}
                onChange={(e) => patch(index, { name: e.target.value })}
              />
              <select
                aria-label={t("opportunities.stageKind", { n: index + 1 })}
                value={row.kind}
                onChange={(e) => patch(index, { kind: e.target.value as StageKind })}
                className={selectClassName()}
              >
                {KINDS.map((k) => (
                  <option key={k.value} value={k.value}>
                    {t(k.label)}
                  </option>
                ))}
              </select>
              <Input
                aria-label={t("opportunities.stageProbability", { n: index + 1 })}
                inputMode="numeric"
                value={row.probability}
                onChange={(e) => patch(index, { probability: e.target.value })}
                className="tabular-nums"
              />
              <span className="flex">
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  aria-label={t("opportunities.moveUp")}
                  disabled={index === 0}
                  onClick={() => move(index, -1)}
                >
                  <ArrowUp className="h-4 w-4" aria-hidden />
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  aria-label={t("opportunities.moveDown")}
                  disabled={index === rows.length - 1}
                  onClick={() => move(index, 1)}
                >
                  <ArrowDown className="h-4 w-4" aria-hidden />
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="ghost"
                  aria-label={t("opportunities.removeStage")}
                  onClick={() => setRows((prev) => prev.filter((_, i) => i !== index))}
                >
                  <Trash2 className="h-4 w-4" aria-hidden />
                </Button>
              </span>
            </li>
          ))}
        </ol>
        <p className="text-xs text-fg-muted">{t("opportunities.stagesHint")}</p>

        <Button
          type="button"
          size="sm"
          variant="secondary"
          onClick={() =>
            setRows((prev) => {
              // New open stages go before the closing ones.
              const at = prev.findIndex((r) => r.kind !== "open");
              const row: Row = {
                key: `n${Date.now()}`,
                code: null,
                name: "",
                kind: "open",
                probability: "50",
              };
              const next = [...prev];
              next.splice(at === -1 ? next.length : at, 0, row);
              return next;
            })
          }
        >
          <Plus className="h-4 w-4" aria-hidden />
          {t("opportunities.addStage")}
        </Button>

        <div className="max-w-xs space-y-1.5">
          <Label htmlFor="pipeline-rotten">{t("opportunities.rottenDays")}</Label>
          <Input
            id="pipeline-rotten"
            inputMode="numeric"
            value={rotten}
            onChange={(e) => setRotten(e.target.value)}
            className="tabular-nums"
          />
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <Button type="button" variant="ghost" onClick={onClose} disabled={update.isPending}>
            {t("actions.cancel")}
          </Button>
          <Button type="submit" loading={update.isPending}>
            {t("common.saveChanges")}
          </Button>
        </div>
      </form>
    </dialog>
  );
}
