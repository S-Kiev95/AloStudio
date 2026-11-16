"use client";

import { Plus, UserMinus, X } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { useAgents } from "@/lib/api/account";
import {
  useSetTeamMembers,
  useTeamMembers,
} from "@/lib/api/teams";
import { useT } from "@/lib/i18n/provider";

export function TeamMembersPanel({
  accountId,
  teamId,
}: {
  accountId: string;
  teamId: number;
}) {
  const t = useT();
  const members = useTeamMembers(accountId, teamId);
  const agents = useAgents(accountId);
  const setMembers = useSetTeamMembers(accountId, teamId);

  const [picking, setPicking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const memberIds = useMemo(
    () => new Set(members.data?.map((m) => m.id) ?? []),
    [members.data],
  );

  const available = useMemo(
    () => (agents.data ?? []).filter((a) => !memberIds.has(a.id)),
    [agents.data, memberIds],
  );

  async function add(userId: number) {
    setError(null);
    try {
      const next = Array.from(new Set([...memberIds, userId]));
      await setMembers.mutateAsync(next);
      setPicking(false);
    } catch (e) {
      setError(
        (e as { message?: string })?.message ?? t("settingsTeams.addMemberFailed"),
      );
    }
  }

  async function remove(userId: number) {
    setError(null);
    try {
      const next = Array.from(memberIds).filter((id) => id !== userId);
      await setMembers.mutateAsync(next);
    } catch (e) {
      setError(
        (e as { message?: string })?.message ?? t("settingsTeams.removeMemberFailed"),
      );
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-fg">{t("settingsTeams.members")}</h3>
        {!picking ? (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => setPicking(true)}
            disabled={available.length === 0}
          >
            <Plus className="h-4 w-4" aria-hidden />
            {t("settingsTeams.addMember")}
          </Button>
        ) : null}
      </div>

      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}

      {picking ? (
        <div className="space-y-2 rounded-md border border-border bg-surface-2 p-3">
          <div className="flex items-center justify-between">
            <p className="text-xs font-medium uppercase text-fg-muted">
              {t("settingsTeams.availableAgents")}
            </p>
            <button
              type="button"
              aria-label={t("actions.close")}
              onClick={() => setPicking(false)}
              className="rounded-md p-1 text-fg-muted hover:bg-surface"
            >
              <X className="h-4 w-4" aria-hidden />
            </button>
          </div>
          {available.length === 0 ? (
            <p className="text-sm text-fg-muted">
              {t("settingsTeams.allMembers")}
            </p>
          ) : (
            <ul className="divide-y divide-border rounded-md border border-border bg-surface">
              {available.map((a) => (
                <li
                  key={a.id}
                  className="flex items-center justify-between px-3 py-2"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm text-fg">{a.name}</p>
                    {a.email ? (
                      <p className="truncate text-xs text-fg-muted">{a.email}</p>
                    ) : null}
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => add(a.id)}
                    loading={setMembers.isPending}
                  >
                    {t("instagram.add")}
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </div>
      ) : null}

      {members.isLoading ? (
        <p className="text-sm text-fg-muted">{t("settingsTeams.loadingMembers")}</p>
      ) : members.isError ? (
        <p role="alert" className="text-sm text-danger">
          {t("settingsTeams.membersLoadFailed")}
        </p>
      ) : (members.data?.length ?? 0) === 0 ? (
        <p className="text-sm text-fg-muted">{t("settingsTeams.noMembers")}</p>
      ) : (
        <ul className="divide-y divide-border rounded-md border border-border bg-surface">
          {members.data?.map((m) => (
            <li key={m.id} className="flex items-center justify-between px-3 py-2">
              <div className="min-w-0">
                <p className="truncate text-sm text-fg">{m.name}</p>
                {m.email ? (
                  <p className="truncate text-xs text-fg-muted">{m.email}</p>
                ) : null}
              </div>
              <button
                type="button"
                aria-label={t("settingsAgents.removeNamed", { name: m.name })}
                title={t("settingsTeams.removeFromTeam")}
                onClick={() => {
                  if (window.confirm(t("settingsTeams.removeConfirm", { name: m.name }))) {
                    void remove(m.id);
                  }
                }}
                disabled={setMembers.isPending}
                className="rounded-md p-1.5 text-fg-muted hover:bg-surface-2 hover:text-danger disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <UserMinus className="h-4 w-4" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
