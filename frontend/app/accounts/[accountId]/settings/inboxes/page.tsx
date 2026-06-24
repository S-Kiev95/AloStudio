import { InboxesView } from "@/components/settings/inboxes/inboxes-view";

export default async function InboxesPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <InboxesView accountId={accountId} />;
}
