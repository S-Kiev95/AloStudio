import { AgentChatView } from "@/components/agent/agent-chat-view";

export default async function AgentThreadPage({
  params,
}: {
  params: Promise<{ accountId: string; threadId: string }>;
}) {
  const { accountId, threadId } = await params;
  const parsed = /^\d+$/.test(threadId) ? Number(threadId) : Number.NaN;
  return <AgentChatView accountId={accountId} threadId={parsed} />;
}
