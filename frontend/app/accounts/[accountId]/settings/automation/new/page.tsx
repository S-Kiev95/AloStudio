import { AutomationRuleNewView } from "@/components/settings/automation/automation-rule-new-view";

export default async function SettingsAutomationNewPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <AutomationRuleNewView accountId={accountId} />;
}
