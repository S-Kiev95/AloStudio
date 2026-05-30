import { MCPTokensView } from "@/components/settings/mcp-tokens/mcp-tokens-view";

export default async function SettingsMCPTokensPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <MCPTokensView accountId={accountId} />;
}
