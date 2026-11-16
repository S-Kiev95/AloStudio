"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type CampaignInput,
  useCampaign,
  useUpdateCampaign,
} from "@/lib/api/campaigns";

import { CampaignAnalyticsPanel } from "./campaign-analytics-panel";
import { CampaignForm } from "./campaign-form";
import { useT } from "@/lib/i18n/provider";

export function CampaignDetailView({
  accountId,
  displayId,
}: {
  accountId: string;
  displayId: number;
}) {
  const t = useT();
  const router = useRouter();
  const { data: campaign, isLoading, isError } = useCampaign(
    accountId,
    displayId,
  );
  const update = useUpdateCampaign(accountId);

  async function handleUpdate(input: CampaignInput) {
    await update.mutateAsync({ displayId, patch: input });
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 md:p-6">
      <Link
        href={`/accounts/${accountId}/campaigns`}
        className="inline-flex items-center gap-1 text-sm text-fg-muted hover:text-fg"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden />
        {t("campaigns.back")}
      </Link>
      {isLoading ? (
        <p className="p-8 text-center text-sm text-fg-muted">{t("common.loading")}</p>
      ) : isError || !campaign ? (
        <p role="alert" className="p-8 text-center text-sm text-danger">
          {t("campaigns.loadFailed")}
        </p>
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle>{campaign.title ?? t("campaigns.untitled")}</CardTitle>
            </CardHeader>
            <CardContent>
              <CampaignForm
                accountId={accountId}
                initial={campaign}
                submitting={update.isPending}
                onSubmit={handleUpdate}
                onCancel={() =>
                  router.push(`/accounts/${accountId}/campaigns`)
                }
              />
            </CardContent>
          </Card>
          <CampaignAnalyticsPanel accountId={accountId} displayId={displayId} />
        </>
      )}
    </div>
  );
}
