import { AgentChatView } from "@/components/agent/agent-chat-view";

export default async function AgentNewChatPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <AgentChatView accountId={accountId} threadId={null} />;
}
