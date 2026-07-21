import { Suspense } from "react";

import { ConversationList } from "@/components/conversations/conversation-list";

export default async function ConversationsPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  // ConversationList reads its state from the URL (useSearchParams), which
  // Next requires to sit under a Suspense boundary.
  return (
    <Suspense>
      <ConversationList accountId={accountId} />
    </Suspense>
  );
}
