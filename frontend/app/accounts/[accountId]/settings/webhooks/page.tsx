import { WebhooksView } from "@/components/settings/webhooks/webhooks-view";

export default async function SettingsWebhooksPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <WebhooksView accountId={accountId} />;
}
