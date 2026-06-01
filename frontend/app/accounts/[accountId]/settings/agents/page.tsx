import { AgentsView } from "@/components/settings/agents/agents-view";

export default async function SettingsAgentsPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <AgentsView accountId={accountId} />;
}
