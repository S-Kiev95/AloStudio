import { AutomationRulesView } from "@/components/settings/automation/automation-rules-view";

export default async function SettingsAutomationPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <AutomationRulesView accountId={accountId} />;
}
