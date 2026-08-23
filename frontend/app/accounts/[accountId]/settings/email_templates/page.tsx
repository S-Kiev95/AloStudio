import { EmailTemplatesView } from "@/components/settings/email-templates/email-templates-view";

export default async function SettingsEmailTemplatesPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <EmailTemplatesView accountId={accountId} />;
}
