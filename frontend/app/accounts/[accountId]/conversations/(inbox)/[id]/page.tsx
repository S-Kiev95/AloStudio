import { ConversationView } from "@/components/conversations/conversation-view";

export default async function ConversationDetailPage({
  params,
}: {
  params: Promise<{ accountId: string; id: string }>;
}) {
  const { accountId, id } = await params;
  return <ConversationView accountId={accountId} displayId={Number(id)} />;
}
