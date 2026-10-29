import { CrmTabs } from "@/components/crm/crm-tabs";

export default async function CrmLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return (
    <div>
      <CrmTabs accountId={accountId} />
      {children}
    </div>
  );
}
