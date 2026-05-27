import { IntegrationAppView } from "@/components/settings/integrations/integration-app-view";

export default async function SettingsIntegrationAppPage({
  params,
}: {
  params: Promise<{ accountId: string; appId: string }>;
}) {
  const { accountId, appId } = await params;
  return <IntegrationAppView accountId={accountId} appId={appId} />;
}
