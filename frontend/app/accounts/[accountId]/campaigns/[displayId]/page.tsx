import { CampaignDetailView } from "@/components/campaigns/campaign-detail-view";

export default async function CampaignDetailPage({
  params,
}: {
  params: Promise<{ accountId: string; displayId: string }>;
}) {
  const { accountId, displayId } = await params;
  return (
    <CampaignDetailView accountId={accountId} displayId={Number(displayId)} />
  );
}
