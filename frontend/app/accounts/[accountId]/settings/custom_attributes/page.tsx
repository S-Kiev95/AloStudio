import { CustomAttributesView } from "@/components/settings/custom-attributes/custom-attributes-view";

export default async function SettingsCustomAttributesPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <CustomAttributesView accountId={accountId} />;
}
