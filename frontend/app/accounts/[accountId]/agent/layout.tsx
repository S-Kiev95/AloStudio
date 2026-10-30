import type { ReactNode } from "react";

import { AgentShell } from "@/components/agent/agent-shell";
import { AgentThreadList } from "@/components/agent/agent-thread-list";

export default async function AgentLayout({
  params,
  children,
}: {
  params: Promise<{ accountId: string }>;
  children: ReactNode;
}) {
  const { accountId } = await params;
  return (
    <AgentShell list={<AgentThreadList accountId={accountId} />}>
      {children}
    </AgentShell>
  );
}
