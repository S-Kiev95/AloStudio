"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type CampaignInput,
  useCreateCampaign,
} from "@/lib/api/campaigns";

import { CampaignForm } from "./campaign-form";
import { useT } from "@/lib/i18n/provider";

export function CampaignNewView({ accountId }: { accountId: string }) {
  const t = useT();
  const router = useRouter();
  const create = useCreateCampaign(accountId);

  async function handleCreate(input: CampaignInput) {
    const c = await create.mutateAsync(input);
    router.push(`/accounts/${accountId}/campaigns/${c.display_id}`);
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
      <Card>
        <CardHeader>
          <CardTitle>{t("campaigns.new")}</CardTitle>
        </CardHeader>
        <CardContent>
          <CampaignForm
            accountId={accountId}
            submitting={create.isPending}
            onSubmit={handleCreate}
            onCancel={() => router.push(`/accounts/${accountId}/campaigns`)}
          />
        </CardContent>
      </Card>
    </div>
  );
}
