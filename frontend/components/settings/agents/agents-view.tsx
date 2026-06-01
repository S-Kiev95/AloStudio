"use client";

import { Mail, Plus, Trash2, User as UserIcon } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
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
import { cn } from "@/lib/utils";

const selectClass =
  "h-11 w-full rounded-md border border-border bg-surface px-3 text-sm text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

export function AgentsView({ accountId }: { accountId: string }) {
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
      return setInviteError("El nombre y el email son obligatorios.");
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
          "No se pudo enviar la invitación.",
      );
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 md:p-6">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-semibold text-fg">Agentes</h2>
        {!showInvite ? (
          <Button size="sm" onClick={() => setShowInvite(true)}>
            <Plus className="h-4 w-4" aria-hidden />
            Invitar agente
          </Button>
        ) : null}
      </div>

      {lastInvited ? (
        <p className="rounded-md border border-success/30 bg-success/5 px-3 py-2 text-sm text-success">
          Le mandamos una invitación a <strong>{lastInvited}</strong>. El
          enlace caduca cuando establezca su contraseña.
        </p>
      ) : null}

      {showInvite ? (
        <Card>
          <CardHeader>
            <CardTitle>Invitar agente</CardTitle>
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
                    Nombre
                  </Label>
                  <Input
                    id="i-name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="i-email" required>
                    Email
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
                <Label htmlFor="i-role">Rol</Label>
                <select
                  id="i-role"
                  className={selectClass}
                  value={role}
                  onChange={(e) => setRole(e.target.value as AgentRole)}
                >
                  <option value="agent">Agente</option>
                  <option value="administrator">Administrador</option>
                </select>
              </div>
              <p className="text-xs text-fg-muted">
                Le va a llegar un email con un enlace para establecer su
                contraseña.
              </p>
              <div className="flex gap-2">
                <Button onClick={submitInvite} loading={invite.isPending}>
                  Enviar invitación
                </Button>
                <Button
                  variant="ghost"
                  onClick={() => {
                    setShowInvite(false);
                    setInviteError(null);
                  }}
                  disabled={invite.isPending}
                >
                  Cancelar
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      ) : null}

      <div className="overflow-hidden rounded-lg border border-border bg-surface">
        {isLoading ? (
          <p className="p-8 text-center text-sm text-fg-muted">Cargando…</p>
        ) : isError ? (
          <p role="alert" className="p-8 text-center text-sm text-danger">
            No se pudieron cargar los agentes.
          </p>
        ) : (data?.length ?? 0) === 0 ? (
          <p className="p-8 text-center text-sm text-fg-muted">
            No hay agentes en esta cuenta todavía.
          </p>
        ) : (
          <ul className="divide-y divide-border">
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
        (e as { message?: string })?.message ?? "No se pudo cambiar el rol.",
      );
    }
  }

  async function onRemove() {
    if (!window.confirm(`¿Quitar a ${agent.name} de la cuenta?`)) return;
    setError(null);
    try {
      await remove.mutateAsync(agent.id);
    } catch (e) {
      setError(
        (e as { message?: string })?.message ?? "No se pudo eliminar.",
      );
    }
  }

  return (
    <li className="flex items-center gap-3 px-4 py-3">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
        <UserIcon className="h-4 w-4" aria-hidden />
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-fg">
          {agent.name}
          {agent.confirmed === false ? (
            <span className="ml-2 rounded bg-warning/10 px-1.5 py-0.5 text-[10px] font-medium uppercase text-warning">
              Pendiente
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
        aria-label="Rol"
        value={currentRole}
        onChange={(e) => changeRole(e.target.value as AgentRole)}
        disabled={update.isPending}
        className={cn(
          "h-9 rounded-md border border-border bg-surface px-2 text-xs text-fg",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        )}
      >
        <option value="agent">{ROLE_LABEL.agent}</option>
        <option value="administrator">{ROLE_LABEL.administrator}</option>
      </select>
      <button
        type="button"
        aria-label={`Quitar a ${agent.name}`}
        title="Quitar de la cuenta"
        onClick={onRemove}
        disabled={remove.isPending}
        className="rounded-md p-1.5 text-fg-muted hover:bg-surface-2 hover:text-danger disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Trash2 className="h-4 w-4" aria-hidden />
      </button>
    </li>
  );
}

