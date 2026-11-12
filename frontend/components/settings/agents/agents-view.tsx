"use client";

import { Mail, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { selectClassName } from "@/components/ui/select";
import {
  type Agent,
  ROLE_ADMINISTRATOR,
  useAgents,
} from "@/lib/api/account";
import {
  type AgentRole,
  ROLE_LABEL,
  useInviteAgent,
  useRemoveAgent,
  useUpdateAgent,
} from "@/lib/api/agents-admin";
import { useT } from "@/lib/i18n/provider";
import { rich } from "@/lib/i18n/rich";

export function AgentsView({ accountId }: { accountId: string }) {
  const t = useT();
  const { data, isLoading, isError } = useAgents(accountId);
  const invite = useInviteAgent(accountId);

  const [showInvite, setShowInvite] = useState(false);
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState<AgentRole>("agent");
  const [inviteError, setInviteError] = useState<string | null>(null);
  const [lastInvited, setLastInvited] = useState<string | null>(null);

  async function submitInvite() {
    setInviteError(null);
    setLastInvited(null);
    if (!email.trim() || !name.trim()) {
      return setInviteError(t("settingsAgents.nameEmailRequired"));
    }
    try {
      await invite.mutateAsync({
        email: email.trim().toLowerCase(),
        name: name.trim(),
        role,
      });
      setLastInvited(email.trim().toLowerCase());
      setEmail("");
      setName("");
      setRole("agent");
      setShowInvite(false);
    } catch (e) {
      setInviteError(
        (e as { message?: string })?.message ??
          t("settingsAgents.inviteFailed"),
      );
    }
  }

  return (
    <div className="max-w-3xl space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-medium text-fg">{t("conversations.reports.agents")}</h2>
        {!showInvite ? (
          <Button size="sm" onClick={() => setShowInvite(true)}>
            <Plus className="h-4 w-4" aria-hidden />
            {t("settingsAgents.invite")}
          </Button>
        ) : null}
      </div>

      {lastInvited ? (
        <p className="rounded-md border border-success/30 bg-success/5 px-3 py-2 text-sm text-success">
          {rich(t("settingsAgents.invited"), {
            email: <strong>{lastInvited}</strong>,
          })}
        </p>
      ) : null}

      {showInvite ? (
        <Card>
          <CardHeader>
            <CardTitle>{t("settingsAgents.invite")}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {inviteError ? (
                <p role="alert" className="text-sm text-danger">
                  {inviteError}
                </p>
              ) : null}
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="i-name" required>
                    {t("profile.name")}
                  </Label>
                  <Input
                    id="i-name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="i-email" required>
                    {t("common.email")}
                  </Label>
                  <Input
                    id="i-email"
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                  />
                </div>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="i-role">{t("settingsAgents.role")}</Label>
                <select
                  id="i-role"
                  className={selectClassName()}
                  value={role}
                  onChange={(e) => setRole(e.target.value as AgentRole)}
                >
                  <option value="agent">{t("settingsAgents.roles.agent")}</option>
                  <option value="administrator">{t("settingsAgents.roles.administrator")}</option>
                </select>
              </div>
              <p className="text-xs text-fg-muted">
                {t("settingsAgents.inviteNote")}
              </p>
              <div className="flex gap-2">
                <Button onClick={submitInvite} loading={invite.isPending}>
                  {t("settingsAgents.sendInvite")}
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => {
                    setShowInvite(false);
                    setInviteError(null);
                  }}
                  disabled={invite.isPending}
                >
                  {t("actions.cancel")}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      ) : null}

      <div className="overflow-hidden rounded-md border border-glass bg-surface">
        {isLoading ? (
          <p className="p-8 text-center text-sm text-fg-muted">{t("common.loading")}</p>
        ) : isError ? (
          <p role="alert" className="p-8 text-center text-sm text-danger">
            {t("settingsAgents.loadFailed")}
          </p>
        ) : (data?.length ?? 0) === 0 ? (
          <p className="p-8 text-center text-sm text-fg-muted">
            {t("settingsAgents.empty")}
          </p>
        ) : (
          <ul className="divide-y divide-glass">
            {data?.map((a) => (
              <AgentRow key={a.id} accountId={accountId} agent={a} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function AgentRow({
  accountId,
  agent,
}: {
  accountId: string;
  agent: Agent;
}) {
  const t = useT();
  const update = useUpdateAgent(accountId);
  const remove = useRemoveAgent(accountId);
  const [error, setError] = useState<string | null>(null);

  const isAdmin = agent.role === ROLE_ADMINISTRATOR;
  const currentRole: AgentRole = isAdmin ? "administrator" : "agent";

  async function changeRole(next: AgentRole) {
    if (next === currentRole) return;
    setError(null);
    try {
      await update.mutateAsync({
        user_id: agent.id,
        patch: { role: next },
      });
    } catch (e) {
      setError(
        (e as { message?: string })?.message ?? t("settingsAgents.roleFailed"),
      );
    }
  }

  async function onRemove() {
    if (!window.confirm(t("settingsAgents.removeConfirm", { name: agent.name }))) return;
    setError(null);
    try {
      await remove.mutateAsync(agent.id);
    } catch (e) {
      setError(
        (e as { message?: string })?.message ?? t("actions.deleteFailed"),
      );
    }
  }

  return (
    <li className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-hover-glass">
      <Avatar name={agent.name || agent.email || "?"} />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-fg">
          {agent.name}
          {agent.confirmed === false ? (
            <span className="ml-2 rounded-sm bg-warning/10 px-1.5 py-0.5 text-[10px] font-medium uppercase text-warning">
              {t("conversations.status.pending")}
            </span>
          ) : null}
        </p>
        {agent.email ? (
          <p className="flex items-center gap-1 text-xs text-fg-muted">
            <Mail className="h-3 w-3" aria-hidden />
            {agent.email}
          </p>
        ) : null}
        {error ? (
          <p role="alert" className="text-xs text-danger">
            {error}
          </p>
        ) : null}
      </div>
      <select
        aria-label={t("settingsAgents.role")}
        value={currentRole}
        onChange={(e) => changeRole(e.target.value as AgentRole)}
        disabled={update.isPending}
        className={selectClassName("sm")}
      >
        <option value="agent">{t(ROLE_LABEL.agent)}</option>
        <option value="administrator">{t(ROLE_LABEL.administrator)}</option>
      </select>
      <button
        type="button"
        aria-label={t("settingsAgents.removeNamed", { name: agent.name })}
        title={t("settingsAgents.removeFromAccount")}
        onClick={onRemove}
        disabled={remove.isPending}
        className="rounded-md p-1.5 text-fg-muted hover:bg-surface-2 hover:text-danger disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Trash2 className="h-4 w-4" aria-hidden />
      </button>
    </li>
  );
}
