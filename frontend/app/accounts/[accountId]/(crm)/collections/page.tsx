import { CollectionsView } from "@/components/crm/collections-view";

export default async function CollectionsPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <CollectionsView accountId={accountId} />;
}
