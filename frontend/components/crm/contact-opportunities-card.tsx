"use client";

import { Plus, TrendingUp } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { type Opportunity, useOpportunities, usePipelines } from "@/lib/api/crm";
import { useIntlTag, useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

import { formatMoney } from "./money";
import { OpportunityDialog } from "./opportunity-dialog";
import { stageLabel } from "./stage-label";

/** A contact's opportunities, on their page, with a shortcut to add one. */
export function ContactOpportunitiesCard({
  accountId,
  contact,
}: {
  accountId: string;
  contact: { id: number; name: string | null };
}) {
  const t = useT();
  const intlTag = useIntlTag();
  const pipelines = usePipelines(accountId);
  const { data, isLoading, isError } = useOpportunities(accountId, { contact_id: contact.id });
  const [editing, setEditing] = useState<Opportunity | null>(null);
  const [creating, setCreating] = useState(false);

  const stages = new Map(
    (pipelines.data ?? []).flatMap((p) => p.stages.map((s) => [s.id, s] as const)),
  );
  const pipelineOf = (o: Opportunity | null) =>
    pipelines.data?.find((p) => p.id === o?.pipeline_id) ?? pipelines.data?.[0];
  const dialogPipeline = pipelineOf(editing);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <TrendingUp className="h-4 w-4 text-fg-muted" aria-hidden />
          {t("opportunities.pageTitle")}
        </CardTitle>
        <Button size="sm" variant="secondary" onClick={() => setCreating(true)} disabled={!pipelines.data}>
          <Plus className="h-4 w-4" aria-hidden />
          {t("opportunities.new")}
        </Button>
      </CardHeader>
      <CardContent>
        {isLoading ? (
          <p className="text-sm text-fg-muted">{t("common.loading")}</p>
        ) : isError ? (
          <p role="alert" className="text-sm text-danger">
            {t("opportunities.loadFailed")}
          </p>
        ) : (data?.length ?? 0) === 0 ? (
          <p className="text-sm text-fg-muted">{t("opportunities.noneForContact")}</p>
        ) : (
          <ul className="divide-y divide-glass">
            {data?.map((o) => {
              const stage = stages.get(o.stage_id);
              return (
                <li key={o.id}>
                  <button
                    type="button"
                    onClick={() => setEditing(o)}
                    className="flex w-full items-center justify-between gap-3 py-2 text-left hover:bg-hover-glass focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon"
                  >
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium text-fg">{o.title}</span>
                      {stage ? (
                        <span
                          className={cn(
                            "text-xs",
                            stage.kind === "won"
                              ? "text-success"
                              : stage.kind === "lost"
                                ? "text-fg-muted line-through"
                                : "text-fg-muted",
                          )}
                        >
                          {stageLabel(t, stage)}
                        </span>
                      ) : null}
                    </span>
                    <span className="shrink-0 font-numeric text-sm tabular-nums text-fg">
                      {o.value != null ? formatMoney(o.value, o.currency, intlTag) : ""}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
      {dialogPipeline ? (
        <OpportunityDialog
          accountId={accountId}
          pipeline={dialogPipeline}
          open={creating || editing !== null}
          initial={editing}
          presetContact={contact}
          onClose={() => {
            setCreating(false);
            setEditing(null);
          }}
        />
      ) : null}
    </Card>
  );
}
