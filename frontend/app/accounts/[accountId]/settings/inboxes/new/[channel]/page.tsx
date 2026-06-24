import { ChannelForm } from "@/components/settings/inboxes/channel-form";

export default async function NewChannelPage({
  params,
}: {
  params: Promise<{ accountId: string; channel: string }>;
}) {
  const { accountId, channel } = await params;
  return <ChannelForm accountId={accountId} channel={channel} />;
}
