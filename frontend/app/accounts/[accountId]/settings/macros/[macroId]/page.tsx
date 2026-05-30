import { MacroDetailView } from "@/components/settings/macros/macro-detail-view";

export default async function SettingsMacroDetailPage({
  params,
}: {
  params: Promise<{ accountId: string; macroId: string }>;
}) {
  const { accountId, macroId } = await params;
  return <MacroDetailView accountId={accountId} macroId={Number(macroId)} />;
}
