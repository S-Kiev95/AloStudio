import { DecisionsView } from "@/components/settings/decisions/decisions-view";

export default async function SettingsDecisionsPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <DecisionsView accountId={accountId} />;
}
