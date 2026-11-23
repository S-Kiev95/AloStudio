import { ClosingSettingsView } from "@/components/closing/closing-settings-view";

export default async function SettingsClosingNotesPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <ClosingSettingsView accountId={accountId} />;
}
