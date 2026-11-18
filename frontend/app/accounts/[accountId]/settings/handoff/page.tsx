import { HandoffSettingsView } from "@/components/handoff/handoff-settings-view";

export default async function SettingsHandoffPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <HandoffSettingsView accountId={accountId} />;
}
