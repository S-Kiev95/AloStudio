import { SignaturesView } from "@/components/settings/signatures/signatures-view";

export default async function SettingsSignaturesPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <SignaturesView accountId={accountId} />;
}
