import { CannedResponsesView } from "@/components/settings/canned-responses/canned-responses-view";

export default async function SettingsCannedResponsesPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <CannedResponsesView accountId={accountId} />;
}
