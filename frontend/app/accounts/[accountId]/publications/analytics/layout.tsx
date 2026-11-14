import { AnalyticsTabs } from "@/components/usage/analytics-tabs";

export default async function AnalyticsLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return (
    <>
      <AnalyticsTabs accountId={accountId} />
      {children}
    </>
  );
}
