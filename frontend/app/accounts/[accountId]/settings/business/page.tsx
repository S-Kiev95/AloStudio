import { BusinessProfileView } from "@/components/settings/business/business-profile-view";

export default async function SettingsBusinessPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <BusinessProfileView accountId={accountId} />;
}
