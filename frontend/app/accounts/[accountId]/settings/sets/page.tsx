import { SetsView } from "@/components/settings/sets/sets-view";

export default async function SettingsSetsPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <SetsView accountId={accountId} />;
}
