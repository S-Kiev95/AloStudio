import { ConversionsView } from "@/components/conversions/conversions-view";

export default async function SettingsConversionsPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <ConversionsView accountId={accountId} />;
}
