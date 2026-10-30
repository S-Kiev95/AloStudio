import { AutopostsView } from "@/components/settings/autoposts/autoposts-view";

export default async function SettingsAutopostsPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <AutopostsView accountId={accountId} />;
}
