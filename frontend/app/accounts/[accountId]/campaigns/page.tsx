import { CampaignsView } from "@/components/campaigns/campaigns-view";

export default async function CampaignsPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <CampaignsView accountId={accountId} />;
}
