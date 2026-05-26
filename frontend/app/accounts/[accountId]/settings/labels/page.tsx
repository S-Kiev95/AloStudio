import { LabelsView } from "@/components/settings/labels/labels-view";

export default async function SettingsLabelsPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <LabelsView accountId={accountId} />;
}
