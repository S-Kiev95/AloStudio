import { PublicationsAnalyticsView } from "@/components/publications/analytics-view";

export default async function PublicationsAnalyticsPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <PublicationsAnalyticsView accountId={accountId} />;
}
