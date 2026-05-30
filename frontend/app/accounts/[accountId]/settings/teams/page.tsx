import { TeamsView } from "@/components/settings/teams/teams-view";

export default async function SettingsTeamsPage({
  params,
}: {
  params: Promise<{ accountId: string }>;
}) {
  const { accountId } = await params;
  return <TeamsView accountId={accountId} />;
}
