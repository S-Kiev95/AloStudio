import { PortalDetailView } from "@/components/help-center/portal-detail-view";

export default async function HelpCenterPortalPage({
  params,
}: {
  params: Promise<{ accountId: string; slug: string }>;
}) {
  const { accountId, slug } = await params;
  return <PortalDetailView accountId={accountId} slug={slug} />;
}
