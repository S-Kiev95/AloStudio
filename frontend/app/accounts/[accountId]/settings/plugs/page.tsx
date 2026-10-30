import { PlugsView } from "@/components/settings/plugs/plugs-view";

export default async function SettingsPlugsPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <PlugsView accountId={accountId} />;
}
