import type { ReactNode } from "react";

import { InboxTabs } from "@/components/conversations/inbox-tabs";

export default async function ConversationsSectionLayout({
  params,
  children,
}: {
  params: Promise<{ accountId: string }>;
  children: ReactNode;
}) {
  const { accountId } = await params;
  return (
    <div>
      <InboxTabs accountId={accountId} />
      {children}
    </div>
  );
}
