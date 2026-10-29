import { Suspense, type ReactNode } from "react";

import { ConversationList } from "@/components/conversations/conversation-list";
import { InboxShell } from "@/components/conversations/inbox-shell";

export default async function InboxThreeColumnLayout({
  params,
  children,
}: {
  params: Promise<{ accountId: string }>;
  children: ReactNode;
}) {
  const { accountId } = await params;
  // ConversationList reads its state from the URL (useSearchParams), which
  // Next requires to sit under a Suspense boundary.
  return (
    <Suspense>
      <InboxShell list={<ConversationList accountId={accountId} />}>
        {children}
      </InboxShell>
    </Suspense>
  );
}
