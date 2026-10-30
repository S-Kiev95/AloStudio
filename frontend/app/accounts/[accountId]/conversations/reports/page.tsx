import { InboxReportsView } from "@/components/conversations/inbox-reports-view";

export default async function InboxReportsPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <InboxReportsView accountId={accountId} />;
}
