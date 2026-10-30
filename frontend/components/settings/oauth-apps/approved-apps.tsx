"use client";

import { AppWindow } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  OAUTH_SCOPE_LABEL,
  type OAuthAuthorization,
  useOAuthAuthorizations,
  useRevokeOAuthAuthorization,
} from "@/lib/api/oauth";

function when(iso: string | null): string {
  return iso ? new Date(iso).toLocaleString() : "Nunca";
}

/** The apps this user authorized in this account, to take access back. */
export function ApprovedApps({ accountId }: { accountId: string }) {
  const { data, isLoading, isError } = useOAuthAuthorizations(accountId);

  return (
    <div className="overflow-hidden rounded-md border border-glass bg-surface">
      {isLoading ? (
        <p className="p-8 text-center text-sm text-fg-muted">Cargando…</p>
      ) : isError ? (
        <p role="alert" className="p-8 text-center text-sm text-danger">
          No se pudieron cargar las apps aprobadas.
        </p>
      ) : (data?.length ?? 0) === 0 ? (
        <p className="p-8 text-center text-sm text-fg-muted">
          No autorizaste ninguna app en esta cuenta.
        </p>
      ) : (
        <ul className="divide-y divide-glass">
          {data?.map((a) => (
            <ApprovedRow key={a.app.id} accountId={accountId} authorization={a} />
          ))}
        </ul>
      )}
    </div>
  );
}

function ApprovedRow({
  accountId,
  authorization,
}: {
  accountId: string;
  authorization: OAuthAuthorization;
}) {
  const revoke = useRevokeOAuthAuthorization(accountId);
  const [error, setError] = useState<string | null>(null);

  async function onRevoke() {
    if (
      !window.confirm(
        `¿Quitarle el acceso a "${authorization.app.name}"? Va a dejar de poder usar tu cuenta.`,
      )
    )
      return;
    setError(null);
    try {
      await revoke.mutateAsync(authorization.app.id);
    } catch (e) {
      setError((e as { message?: string })?.message ?? "No se pudo quitar el acceso.");
    }
  }

  return (
    <li className="flex flex-wrap items-center gap-3 px-4 py-3">
      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-focused text-lit">
        <AppWindow className="h-4 w-4" aria-hidden />
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-fg">{authorization.app.name}</p>
        <p className="font-numeric text-xs tabular-nums text-fg-muted">
          {OAUTH_SCOPE_LABEL[authorization.scope]} · Autorizada{" "}
          {when(authorization.authorized_at)} · Último uso{" "}
          {when(authorization.last_used_at)}
        </p>
        {error ? (
          <p role="alert" className="text-xs text-danger">
            {error}
          </p>
        ) : null}
      </div>
      <Button
        type="button"
        variant="secondary"
        size="sm"
        loading={revoke.isPending}
        onClick={() => void onRevoke()}
      >
        Quitar acceso
      </Button>
    </li>
  );
}
