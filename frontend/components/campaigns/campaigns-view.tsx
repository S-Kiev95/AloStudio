"use client";

import { ChevronRight, Megaphone, Plus, Send, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { PageHeader } from "@/components/shell/page-header";
import { buttonVariants } from "@/components/ui/button";
import { SegmentedControl } from "@/components/ui/segmented-control";
import {
  type Campaign,
  type CampaignType,
  useCampaigns,
  useDeleteCampaign,
} from "@/lib/api/campaigns";
import { cn } from "@/lib/utils";
import { INTL_TAGS } from "@/lib/i18n/config";
import { useLocale, useT } from "@/lib/i18n/provider";
import type { MessageKey } from "@/lib/i18n/translate";

const TYPE_FILTERS: { value: CampaignType | undefined; label: MessageKey }[] = [
  { value: undefined, label: "campaigns.filters.all" },
  { value: "ongoing", label: "campaigns.filters.ongoing" },
  { value: "one_off", label: "campaigns.filters.oneOff" },
];

const TYPE_LABEL: Record<CampaignType, MessageKey> = {
  ongoing: "campaigns.type.ongoing",
  one_off: "campaigns.type.oneOff",
};

export function CampaignsView({ accountId }: { accountId: string }) {
  const t = useT();
  const [type, setType] = useState<CampaignType | undefined>(undefined);
  const { data, isLoading, isError } = useCampaigns(accountId);

  const filtered = type
    ? (data ?? []).filter((c) => c.campaign_type === type)
    : (data ?? []);

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <PageHeader
        title={t("nav.campaigns")}
        actions={
          <Link
            href={`/accounts/${accountId}/campaigns/new`}
            className={buttonVariants({ size: "sm" })}
          >
            <Plus className="h-4 w-4" aria-hidden />
            {t("campaigns.new")}
          </Link>
        }
      />

      <SegmentedControl
        ariaLabel={t("campaigns.filterLabel")}
        size="sm"
        value={type}
        onValueChange={setType}
        options={TYPE_FILTERS.map((o) => ({ ...o, label: t(o.label) }))}
      />

      <div className="overflow-hidden rounded-md border border-glass bg-surface">
        {isLoading ? (
          <p className="p-8 text-center text-sm text-fg-muted">{t("common.loading")}</p>
        ) : isError ? (
          <p role="alert" className="p-8 text-center text-sm text-danger">
            {t("campaigns.listLoadFailed")}
          </p>
        ) : filtered.length === 0 ? (
          <p className="p-8 text-center text-sm text-fg-muted">
            {t("campaigns.empty")}
          </p>
        ) : (
          <ul className="divide-y divide-glass">
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
  const t = useT();
  const locale = useLocale();
  const del = useDeleteCampaign(accountId);
  const [error, setError] = useState<string | null>(null);

  async function onDelete(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (!window.confirm(t("campaigns.deleteConfirm", { title: campaign.title ?? "" })))
      return;
    setError(null);
    try {
      await del.mutateAsync(campaign.display_id);
    } catch (err) {
      setError(
        (err as { message?: string })?.message ?? t("actions.deleteFailed"),
      );
    }
  }

  const when =
    campaign.campaign_type === "one_off" && campaign.scheduled_at
      ? t("campaigns.scheduledAt", {
          when: new Date(campaign.scheduled_at).toLocaleString(INTL_TAGS[locale]),
        })
      : campaign.campaign_status === "completed"
        ? t("campaigns.completed")
        : t("campaigns.active");

  const ongoing = campaign.campaign_type === "ongoing";
  const TypeIcon = ongoing ? Megaphone : Send;

  return (
    <li className="flex items-center gap-1 pr-2 transition-colors hover:bg-hover-glass">
      <Link
        href={`/accounts/${accountId}/campaigns/${campaign.display_id}`}
        className="flex min-w-0 flex-1 items-center gap-3 px-4 py-3 focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-neon"
      >
        <span
          className={cn(
            "flex h-9 w-9 shrink-0 items-center justify-center rounded-md",
            ongoing ? "bg-focused text-lit" : "bg-info/10 text-info",
          )}
        >
          <TypeIcon className="h-4 w-4" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-fg">
            {campaign.title ?? <span className="text-fg-muted">{t("campaigns.untitledParen")}</span>}
          </p>
          <p className="truncate font-numeric text-xs tabular-nums text-fg-muted">
            {when}
          </p>
          {error ? (
            <p role="alert" className="text-xs text-danger">
              {error}
            </p>
          ) : null}
        </div>
        <span className="rounded-pill bg-surface-2 px-2 py-0.5 text-xs font-medium text-fg-muted">
          {t(TYPE_LABEL[campaign.campaign_type])}
        </span>
        <span
          className={cn(
            "rounded-pill px-2 py-0.5 text-xs font-medium",
            campaign.enabled
              ? "bg-success/10 text-success"
              : "bg-surface-2 text-fg-muted",
          )}
        >
          {campaign.enabled ? t("campaigns.active") : t("campaigns.inactive")}
        </span>
      </Link>
      <button
        type="button"
        aria-label={t("actions.delete")}
        title={t("actions.delete")}
        onClick={onDelete}
        disabled={del.isPending}
        className="rounded-md p-1.5 text-fg-muted hover:bg-hover-glass hover:text-danger disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon"
      >
        <Trash2 className="h-4 w-4" aria-hidden />
      </button>
      <ChevronRight className="h-4 w-4 shrink-0 text-fg-muted" aria-hidden />
    </li>
  );
}
