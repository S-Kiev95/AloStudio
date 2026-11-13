import { CompanyDetailView } from "@/components/crm/company-detail-view";

export default async function CompanyPage({
  params,
}: {
  params: Promise<{ accountId: string; companyId: string }>;
}) {
  const { accountId, companyId } = await params;
  return <CompanyDetailView accountId={accountId} companyId={Number(companyId)} />;
}
