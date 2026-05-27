import { AgentBotsView } from "@/components/settings/agent-bots/agent-bots-view";

export default async function SettingsAgentBotsPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <AgentBotsView accountId={accountId} />;
}
