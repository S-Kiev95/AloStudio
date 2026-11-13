"use client";

import { AlarmClock, Plus, Search, Settings2 } from "lucide-react";
import { useMemo, useState } from "react";

import { PageHeader } from "@/components/shell/page-header";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { selectClassName } from "@/components/ui/select";
import { SegmentedControl } from "@/components/ui/segmented-control";
import {
  daysIdle,
  type Opportunity,
  type Pipeline,
  type Stage,
  useOpportunities,
  usePipelines,
  useUpdateOpportunity,
} from "@/lib/api/crm";
import { useIsAccountAdmin, useProfile } from "@/lib/api/profile";
import { useIntlTag, useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

import { formatMoney, formatTotals } from "./money";
import { OpportunityDialog } from "./opportunity-dialog";
import { PipelineDialog } from "./pipeline-dialog";
import { pipelineLabel, stageLabel } from "./stage-label";

type Scope = "all" | "mine";

/** The sales board: one column per stage of the chosen pipeline. Cards move
 *  between columns by dragging, or from the card's own form. */
export function OpportunitiesView({ accountId }: { accountId: string }) {
  const t = useT();
  const intlTag = useIntlTag();
  const isAdmin = useIsAccountAdmin(accountId);
  const profile = useProfile();
  const pipelines = usePipelines(accountId);
  const [pipelineId, setPipelineId] = useState<number | null>(null);
  const [scope, setScope] = useState<Scope>("all");
  const [query, setQuery] = useState("");
  const [editing, setEditing] = useState<Opportunity | null>(null);
  const [creatingIn, setCreatingIn] = useState<number | null | undefined>(undefined);
  const [editingPipeline, setEditingPipeline] = useState(false);
  const [moveError, setMoveError] = useState<string | null>(null);

  const pipeline: Pipeline | undefined =
    pipelines.data?.find((p) => p.id === pipelineId) ?? pipelines.data?.[0];
  const opportunities = useOpportunities(accountId, {
    pipeline_id: pipeline?.id,
    owner_id: scope === "mine" ? profile.data?.id : undefined,
    q: query.trim() || undefined,
  });
  const update = useUpdateOpportunity(accountId);

  const byStage = useMemo(() => {
    const map = new Map<number, Opportunity[]>();
    for (const o of opportunities.data ?? []) {
      map.set(o.stage_id, [...(map.get(o.stage_id) ?? []), o]);
    }
    return map;
  }, [opportunities.data]);

  async function moveTo(opportunity: Opportunity, stage: Stage) {
    if (opportunity.stage_id === stage.id) return;
    setMoveError(null);
    try {
      await update.mutateAsync({ id: opportunity.id, patch: { stage_id: stage.id } });
    } catch (err) {
      setMoveError((err as { message?: string })?.message ?? t("opportunities.moveFailed"));
    }
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title={t("opportunities.pageTitle")}
        actions={
          <span className="flex gap-2">
            {isAdmin && pipeline ? (
              <Button size="sm" variant="secondary" onClick={() => setEditingPipeline(true)}>
                <Settings2 className="h-4 w-4" aria-hidden />
                {t("opportunities.editStages")}
              </Button>
            ) : null}
            <Button size="sm" onClick={() => setCreatingIn(null)} disabled={!pipeline}>
              <Plus className="h-4 w-4" aria-hidden />
              {t("opportunities.new")}
            </Button>
          </span>
        }
      />

      <div className="flex flex-wrap items-center gap-3">
        {(pipelines.data?.length ?? 0) > 1 ? (
          <select
            aria-label={t("opportunities.pipeline")}
            value={pipeline?.id ?? ""}
            onChange={(e) => setPipelineId(Number(e.target.value))}
            className={cn(selectClassName("sm"), "w-auto")}
          >
            {pipelines.data?.map((p) => (
              <option key={p.id} value={p.id}>
                {pipelineLabel(t, p)}
              </option>
            ))}
          </select>
        ) : null}
        <SegmentedControl
          ariaLabel={t("opportunities.scope")}
          size="sm"
          value={scope}
          onValueChange={setScope}
          options={[
            { value: "all", label: t("opportunities.all") },
            { value: "mine", label: t("opportunities.mine") },
          ]}
        />
        <div className="relative w-64 max-w-full">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-muted"
            aria-hidden
          />
          <Input
            aria-label={t("opportunities.search")}
            placeholder={t("opportunities.search")}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="h-9 pl-9"
          />
        </div>
      </div>

      {moveError ? (
        <p role="alert" className="text-sm text-danger">
          {moveError}
        </p>
      ) : null}

      {pipelines.isLoading || opportunities.isLoading ? (
        <p className="p-8 text-center text-sm text-fg-muted">{t("common.loading")}</p>
      ) : pipelines.isError || opportunities.isError || !pipeline ? (
        <p role="alert" className="p-8 text-center text-sm text-danger">
          {t("opportunities.loadFailed")}
        </p>
      ) : (
        <div className="flex gap-3 overflow-x-auto pb-2">
          {pipeline.stages.map((stage) => (
            <StageColumn
              key={stage.id}
              stage={stage}
              items={byStage.get(stage.id) ?? []}
              rottenDays={pipeline.rotten_days}
              intlTag={intlTag}
              onOpen={setEditing}
              onAdd={() => setCreatingIn(stage.id)}
              onDropOpportunity={(id) => {
                const o = opportunities.data?.find((x) => x.id === id);
                if (o) void moveTo(o, stage);
              }}
            />
          ))}
        </div>
      )}

      {pipeline ? (
        <OpportunityDialog
          accountId={accountId}
          pipeline={pipeline}
          open={editing !== null || creatingIn !== undefined}
          initial={editing}
          defaultStageId={creatingIn ?? null}
          onClose={() => {
            setEditing(null);
            setCreatingIn(undefined);
          }}
        />
      ) : null}
      {pipeline && editingPipeline ? (
        <PipelineDialog
          accountId={accountId}
          pipeline={pipeline}
          open={editingPipeline}
          onClose={() => setEditingPipeline(false)}
        />
      ) : null}
    </div>
  );
}

function StageColumn({
  stage,
  items,
  rottenDays,
  intlTag,
  onOpen,
  onAdd,
  onDropOpportunity,
}: {
  stage: Stage;
  items: Opportunity[];
  rottenDays: number;
  intlTag: string;
  onOpen: (o: Opportunity) => void;
  onAdd: () => void;
  onDropOpportunity: (id: number) => void;
}) {
  const t = useT();
  const [over, setOver] = useState(false);
  const label = stageLabel(t, stage);
  const totals = formatTotals(items, intlTag);

  return (
    <section
      aria-label={label}
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        const id = Number(e.dataTransfer.getData("text/plain"));
        if (id) onDropOpportunity(id);
      }}
      className={cn(
        "flex w-72 shrink-0 flex-col rounded-panel border border-glass bg-surface",
        over && "border-neon",
      )}
    >
      <header className="space-y-0.5 border-b border-glass px-3 py-2.5">
        <div className="flex items-center justify-between gap-2">
          <h2
            className={cn(
              "truncate text-sm font-medium",
              stage.kind === "won" ? "text-success" : stage.kind === "lost" ? "text-fg-muted" : "text-fg",
            )}
          >
            {label}
          </h2>
          <span className="font-numeric text-xs tabular-nums text-fg-muted">{items.length}</span>
        </div>
        <p className="font-numeric text-xs tabular-nums text-fg-muted">
          {totals ?? "—"}
          {stage.kind === "open" ? ` · ${stage.probability}%` : ""}
        </p>
      </header>
      <ul className="flex min-h-24 flex-1 flex-col gap-2 p-2">
        {items.map((o) => (
          <li key={o.id}>
            <OpportunityCard
              opportunity={o}
              stale={stage.kind === "open" && daysIdle(o) > rottenDays}
              intlTag={intlTag}
              onOpen={() => onOpen(o)}
            />
          </li>
        ))}
      </ul>
      {stage.kind === "open" ? (
        <button
          type="button"
          onClick={onAdd}
          className="m-2 mt-0 flex items-center justify-center gap-1.5 rounded-md py-1.5 text-xs text-fg-muted hover:bg-hover-glass hover:text-fg focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon"
        >
          <Plus className="h-3.5 w-3.5" aria-hidden />
          {t("opportunities.addHere")}
        </button>
      ) : null}
    </section>
  );
}

function OpportunityCard({
  opportunity: o,
  stale,
  intlTag,
  onOpen,
}: {
  opportunity: Opportunity;
  stale: boolean;
  intlTag: string;
  onOpen: () => void;
}) {
  const t = useT();
  const overdue =
    o.closed_at == null &&
    o.expected_close_on != null &&
    o.expected_close_on < new Date().toISOString().slice(0, 10);
  return (
    <button
      type="button"
      draggable
      onDragStart={(e) => {
        e.dataTransfer.setData("text/plain", String(o.id));
        e.dataTransfer.effectAllowed = "move";
      }}
      onClick={onOpen}
      className="w-full space-y-1.5 rounded-md border border-glass bg-surface-2 p-2.5 text-left hover:border-neon/60 focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon"
    >
      <p className="line-clamp-2 text-sm font-medium text-fg">{o.title}</p>
      {o.contact ? (
        <p className="flex items-center gap-1.5 truncate text-xs text-fg-muted">
          <Avatar name={o.contact.name ?? "?"} src={o.contact.avatar_url} size="xs" />
          {o.contact.name || t("conversations.contact.fallbackName", { id: o.contact.id })}
        </p>
      ) : null}
      <div className="flex items-center justify-between gap-2 text-xs">
        <span className="font-numeric tabular-nums text-fg">
          {o.value != null ? formatMoney(o.value, o.currency, intlTag) : ""}
        </span>
        <span className="flex items-center gap-1.5">
          {o.expected_close_on ? (
            <span
              className={cn("font-numeric tabular-nums", overdue ? "text-danger" : "text-fg-muted")}
              title={t("opportunities.expectedClose")}
            >
              {new Date(`${o.expected_close_on}T00:00:00`).toLocaleDateString(intlTag, {
                day: "numeric",
                month: "short",
              })}
            </span>
          ) : null}
          {stale ? (
            <AlarmClock
              className="h-3.5 w-3.5 text-warning"
              aria-label={t("opportunities.stale")}
            />
          ) : null}
          {o.owner ? <Avatar name={o.owner.name} size="xs" /> : null}
        </span>
      </div>
    </button>
  );
}
