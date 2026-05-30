import { IntegrationsView } from "@/components/settings/integrations/integrations-view";

export default async function SettingsIntegrationsPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <IntegrationsView accountId={accountId} />;
}
