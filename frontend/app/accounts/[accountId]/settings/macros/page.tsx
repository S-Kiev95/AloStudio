import { MacrosView } from "@/components/settings/macros/macros-view";

export default async function SettingsMacrosPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <MacrosView accountId={accountId} />;
}
