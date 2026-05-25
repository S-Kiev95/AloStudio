import { ConversationList } from "@/components/conversations/conversation-list";

export default async function ConversationsPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <ConversationList accountId={accountId} />;
}
