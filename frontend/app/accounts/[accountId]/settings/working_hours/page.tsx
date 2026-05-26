import { WorkingHoursView } from "@/components/settings/working-hours/working-hours-view";

export default async function SettingsWorkingHoursPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <WorkingHoursView accountId={accountId} />;
}
