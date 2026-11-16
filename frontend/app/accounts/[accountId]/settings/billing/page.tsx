import { BillingView } from "@/components/billing/billing-view";

export default async function SettingsBillingPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <BillingView accountId={accountId} />;
}
