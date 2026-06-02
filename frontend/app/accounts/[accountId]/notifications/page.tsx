import { NotificationsPage } from "@/components/notifications/notifications-page";

export default async function NotificationsRoute({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <NotificationsPage accountId={accountId} />;
}
