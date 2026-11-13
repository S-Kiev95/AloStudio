import { OpportunitiesView } from "@/components/crm/opportunities-view";

export default async function OpportunitiesPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <OpportunitiesView accountId={accountId} />;
}
