import { AccountOverview } from "@/components/overview/account-overview";

/**
 * Account overview (Inicio). Rendered inside the dashboard shell (F.2) — live
 * state counters, the 7-day KPI set, a conversations chart, and quick links,
 * all driven by the reports/live-metrics endpoints.
 */
export default async function AccountHome({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <AccountOverview accountId={accountId} />;
}
