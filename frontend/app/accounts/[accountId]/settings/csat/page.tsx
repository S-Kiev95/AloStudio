import { CsatView } from "@/components/settings/csat/csat-view";

export default async function SettingsCsatPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <CsatView accountId={accountId} />;
}
