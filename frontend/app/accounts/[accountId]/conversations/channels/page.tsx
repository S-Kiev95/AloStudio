import { InboxChannelsView } from "@/components/conversations/inbox-channels-view";

export default async function InboxChannelsPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <InboxChannelsView accountId={accountId} />;
}
