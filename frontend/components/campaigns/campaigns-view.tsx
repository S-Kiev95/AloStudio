"use client";

import { ChevronRight, Megaphone, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { buttonVariants } from "@/components/ui/button";
import {
  type Campaign,
  type CampaignType,
  useCampaigns,
  useDeleteCampaign,
} from "@/lib/api/campaigns";
import { cn } from "@/lib/utils";

const TYPE_FILTERS: { value: CampaignType | undefined; label: string }[] = [
  { value: undefined, label: "Todas" },
  { value: "ongoing", label: "Continuas" },
  { value: "one_off", label: "Puntuales" },
];

const TYPE_LABEL: Record<CampaignType, string> = {
  ongoing: "Continua",
  one_off: "Puntual",
};

export function CampaignsView({ accountId }: { accountId: string }) {
  const [type, setType] = useState<CampaignType | undefined>(undefined);
  const { data, isLoading, isError } = useCampaigns(accountId);

  const filtered = type
    ? (data ?? []).filter((c) => c.campaign_type === type)
    : (data ?? []);

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 md:p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-fg">Campañas</h2>
        <Link
          href={`/accounts/${accountId}/campaigns/new`}
          className={buttonVariants({ size: "sm" })}
        >
          <Plus className="h-4 w-4" aria-hidden />
          Nueva campaña
        </Link>
      </div>

      <div className="flex flex-wrap gap-2">
        {TYPE_FILTERS.map((f) => (
          <button
            key={f.label}
            type="button"
            onClick={() => setType(f.value)}
            aria-pressed={type === f.value}
            className={cn(
              "rounded-md px-3 py-1.5 text-sm font-medium",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              type === f.value
                ? "bg-primary text-primary-fg"
                : "border border-border bg-surface text-fg hover:bg-surface-2",
            )}
          >
            {f.label}
          </button>
        ))}
      </div>

      <div className="overflow-hidden rounded-lg border border-border bg-surface">
        {isLoading ? (
          <p className="p-8 text-center text-sm text-fg-muted">Cargando…</p>
        ) : isError ? (
          <p role="alert" className="p-8 text-center text-sm text-danger">
            No se pudieron cargar las campañas.
          </p>
        ) : filtered.length === 0 ? (
          <p className="p-8 text-center text-sm text-fg-muted">
            No hay campañas en este filtro.
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {filtered.map((c) => (
              <CampaignRow key={c.display_id} accountId={accountId} campaign={c} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function CampaignRow({
  accountId,
  campaign,
}: {
  accountId: string;
  campaign: Campaign;
}) {
  const del = useDeleteCampaign(accountId);
  const [error, setError] = useState<string | null>(null);

  async function onDelete(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (!window.confirm(`¿Eliminar la campaña "${campaign.title ?? ""}"?`))
      return;
    setError(null);
    try {
      await del.mutateAsync(campaign.display_id);
    } catch (err) {
      setError(
        (err as { message?: string })?.message ?? "No se pudo eliminar.",
      );
    }
  }

  const when =
    campaign.campaign_type === "one_off" && campaign.scheduled_at
      ? `Programada ${new Date(campaign.scheduled_at).toLocaleString()}`
      : campaign.campaign_status === "completed"
        ? "Completada"
        : "Activa";

  return (
    <li className="flex items-center gap-1 pr-2 hover:bg-surface-2">
      <Link
        href={`/accounts/${accountId}/campaigns/${campaign.display_id}`}
        className="flex min-w-0 flex-1 items-center gap-3 px-4 py-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
      >
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
          <Megaphone className="h-4 w-4" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-fg">
            {campaign.title ?? <span className="text-fg-muted">(sin título)</span>}
          </p>
          <p className="truncate text-xs text-fg-muted">{when}</p>
          {error ? (
            <p role="alert" className="text-xs text-danger">
              {error}
            </p>
          ) : null}
        </div>
        <span className="rounded-full bg-surface-2 px-2 py-0.5 text-xs font-medium text-fg-muted">
          {TYPE_LABEL[campaign.campaign_type]}
        </span>
        <span
          className={cn(
            "rounded-full px-2 py-0.5 text-xs font-medium",
            campaign.enabled
              ? "bg-success/10 text-success"
              : "bg-surface-2 text-fg-muted",
          )}
        >
          {campaign.enabled ? "Activa" : "Inactiva"}
        </span>
      </Link>
      <button
        type="button"
        aria-label="Eliminar"
        title="Eliminar"
        onClick={onDelete}
        disabled={del.isPending}
        className="rounded-md p-1.5 text-fg-muted hover:bg-surface hover:text-danger disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Trash2 className="h-4 w-4" aria-hidden />
      </button>
      <ChevronRight className="h-4 w-4 shrink-0 text-fg-muted" aria-hidden />
    </li>
  );
}
