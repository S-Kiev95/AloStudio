import { MacroNewView } from "@/components/settings/macros/macro-new-view";

export default async function SettingsMacroNewPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <MacroNewView accountId={accountId} />;
}
