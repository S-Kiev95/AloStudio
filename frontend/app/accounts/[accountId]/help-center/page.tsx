import { PortalsView } from "@/components/help-center/portals-view";

export default async function HelpCenterPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <PortalsView accountId={accountId} />;
}
