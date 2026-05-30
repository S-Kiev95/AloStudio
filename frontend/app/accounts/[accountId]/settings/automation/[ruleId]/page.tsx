import { AutomationRuleDetailView } from "@/components/settings/automation/automation-rule-detail-view";

export default async function SettingsAutomationDetailPage({
  params,
}: {
  params: Promise<{ accountId: string; ruleId: string }>;
}) {
  const { accountId, ruleId } = await params;
  return (
    <AutomationRuleDetailView accountId={accountId} ruleId={Number(ruleId)} />
  );
}
