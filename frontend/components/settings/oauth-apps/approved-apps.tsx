"use client";

import { AppWindow } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import {
  type OAuthAuthorization,
  useOAuthAuthorizations,
  useRevokeOAuthAuthorization,
} from "@/lib/api/oauth";
import { useIntlTag, useT } from "@/lib/i18n/provider";
import type { Translate } from "@/lib/i18n/translate";

function when(iso: string | null, t: Translate, intlTag: string): string {
  return iso ? new Date(iso).toLocaleString(intlTag) : t("settingsOauth.never");
}

/** The apps this user authorized in this account, to take access back. */
export function ApprovedApps({ accountId }: { accountId: string }) {
  const t = useT();
  const { data, isLoading, isError } = useOAuthAuthorizations(accountId);

  return (
    <div className="overflow-hidden rounded-md border border-glass bg-surface">
      {isLoading ? (
        <p className="p-8 text-center text-sm text-fg-muted">{t("common.loading")}</p>
      ) : isError ? (
        <p role="alert" className="p-8 text-center text-sm text-danger">
          {t("settingsOauth.approvedLoadFailed")}
        </p>
      ) : (data?.length ?? 0) === 0 ? (
        <p className="p-8 text-center text-sm text-fg-muted">
          {t("settingsOauth.noneApproved")}
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
  const t = useT();
  const intlTag = useIntlTag();
  const revoke = useRevokeOAuthAuthorization(accountId);
  const [error, setError] = useState<string | null>(null);

  async function onRevoke() {
    if (
      !window.confirm(
        t("settingsOauth.revokeConfirm", { name: authorization.app.name }),
      )
    )
      return;
    setError(null);
    try {
      await revoke.mutateAsync(authorization.app.id);
    } catch (e) {
      setError((e as { message?: string })?.message ?? t("settingsOauth.revokeFailed"));
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
          {t("settingsOauth.authorizedLine", {
            scope: t(`settingsOauth.scope.${authorization.scope}`),
            authorized: when(authorization.authorized_at, t, intlTag),
            lastUsed: when(authorization.last_used_at, t, intlTag),
          })}
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
        {t("settingsOauth.revoke")}
      </Button>
    </li>
  );
}
