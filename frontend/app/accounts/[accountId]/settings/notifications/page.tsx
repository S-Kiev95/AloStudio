import { NotificationsSettingsView } from "@/components/settings/notifications/notifications-settings-view";

export default async function SettingsNotificationsPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <NotificationsSettingsView accountId={accountId} />;
}
