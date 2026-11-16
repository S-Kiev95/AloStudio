import { CompaniesView } from "@/components/crm/companies-view";

export default async function CompaniesPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <CompaniesView accountId={accountId} />;
}
