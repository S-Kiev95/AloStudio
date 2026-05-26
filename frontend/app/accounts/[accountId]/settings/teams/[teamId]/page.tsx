import { TeamDetailView } from "@/components/settings/teams/team-detail-view";

export default async function SettingsTeamDetailPage({
  params,
}: {
  params: Promise<{ accountId: string; teamId: string }>;
}) {
  const { accountId, teamId } = await params;
  return <TeamDetailView accountId={accountId} teamId={Number(teamId)} />;
}
