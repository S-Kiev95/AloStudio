import { OAuthAppsView } from "@/components/settings/oauth-apps/oauth-apps-view";

export default async function SettingsOAuthAppsPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <OAuthAppsView accountId={accountId} />;
}
