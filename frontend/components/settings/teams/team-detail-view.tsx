"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { type TeamInput, useTeam, useUpdateTeam } from "@/lib/api/teams";

import { TeamForm } from "./team-form";
import { TeamMembersPanel } from "./team-members-panel";
import { useT } from "@/lib/i18n/provider";

export function TeamDetailView({
  accountId,
  teamId,
}: {
  accountId: string;
  teamId: number;
}) {
  const t = useT();
  const { data: team, isLoading, isError } = useTeam(accountId, teamId);
  const update = useUpdateTeam(accountId);

  async function handleUpdate(input: TeamInput) {
    await update.mutateAsync({ id: teamId, patch: input });
  }

  return (
    <div className="max-w-3xl space-y-4">
      <Link
        href={`/accounts/${accountId}/settings/teams`}
        className="inline-flex items-center gap-1 text-sm text-fg-muted hover:text-fg"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden />
        {t("settingsTeams.back")}
      </Link>

      {isLoading ? (
        <p className="p-8 text-center text-sm text-fg-muted">{t("common.loading")}</p>
      ) : isError || !team ? (
        <p role="alert" className="p-8 text-center text-sm text-danger">
          {t("settingsTeams.loadFailed")}
        </p>
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle>{team.name}</CardTitle>
            </CardHeader>
            <CardContent>
              <TeamForm
                initial={team}
                submitting={update.isPending}
                onSubmit={handleUpdate}
                onCancel={() => {
                  /* no-op — form keeps its own state on cancel */
                }}
                submitLabel={t("common.saveChanges")}
              />
            </CardContent>
          </Card>

          <Card>
            <CardContent className="pt-6">
              <TeamMembersPanel accountId={accountId} teamId={teamId} />
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
