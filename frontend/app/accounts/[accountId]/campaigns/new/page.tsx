import { CampaignNewView } from "@/components/campaigns/campaign-new-view";

export default async function CampaignNewPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <CampaignNewView accountId={accountId} />;
}
