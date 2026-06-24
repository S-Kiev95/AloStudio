import { InboxDetailView } from "@/components/settings/inboxes/inbox-detail-view";

export default async function InboxDetailPage({
  params,
}: {
  params: Promise<{ accountId: string; inboxId: string }>;
}) {
  const { accountId, inboxId } = await params;
  return <InboxDetailView accountId={accountId} inboxId={Number(inboxId)} />;
}
