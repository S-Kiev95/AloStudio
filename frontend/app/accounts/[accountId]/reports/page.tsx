import { ReportsView } from "@/components/reports/reports-view";

export default async function ReportsPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <ReportsView accountId={accountId} />;
}
