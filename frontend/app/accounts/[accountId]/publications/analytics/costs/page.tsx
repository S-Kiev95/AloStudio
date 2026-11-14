import { CostsView } from "@/components/usage/costs-view";

export default async function CostsPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <CostsView accountId={accountId} />;
}
