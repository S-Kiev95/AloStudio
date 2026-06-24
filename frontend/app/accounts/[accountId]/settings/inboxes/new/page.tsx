import { ChannelPicker } from "@/components/settings/inboxes/channel-picker";

export default async function NewInboxPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <ChannelPicker accountId={accountId} />;
}
