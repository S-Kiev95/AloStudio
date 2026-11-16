"use client";

import { AppWindow, Check } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  type OAuthConsent as OAuthConsentData,
  type OAuthScope,
  useOAuthConsent,
  useSubmitOAuthConsent,
} from "@/lib/api/oauth";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n/provider";
import { rich } from "@/lib/i18n/rich";
import type { MessageKey } from "@/lib/i18n/translate";

const SCOPE_POINTS: Record<OAuthScope, MessageKey[]> = {
  read: ["oauth.scope.readPosts", "oauth.scope.readConversations"],
  write: [
    "oauth.scope.readPosts",
    "oauth.scope.readConversations",
    "oauth.scope.writePosts",
    "oauth.scope.writeConversations",
  ],
};

function errorMessage(e: unknown, fallback: string): string {
  return (e as { message?: string })?.message ?? fallback;
}

function hostOf(uri: string): string {
  try {
    return new URL(uri).host;
  } catch {
    return uri;
  }
}

/** The OAuth consent: which app asks for what, on which account. Without a
 *  session ``apiFetch`` sends the user to the login, which comes back here. */
export function OAuthConsent() {
  const t = useT();
  const searchParams = useSearchParams();
  const search = searchParams.toString() ? `?${searchParams.toString()}` : "";
  const consent = useOAuthConsent(search);
  const redirectTo =
    consent.data && "redirect_to" in consent.data ? consent.data.redirect_to : null;

  useEffect(() => {
    // An invalid request goes straight back to the app with its error.
    if (redirectTo) window.location.assign(redirectTo);
  }, [redirectTo]);

  if (consent.isLoading || redirectTo) {
    return <p className="text-sm text-fg-muted">{t("common.loading")}</p>;
  }
  if (consent.isError || !consent.data || "redirect_to" in consent.data) {
    return (
      <div className="space-y-4">
        <h1 className="text-xl font-medium text-fg">{t("oauth.cannotAuthorize")}</h1>
        <p role="alert" className="text-sm text-danger">
          {errorMessage(consent.error, t("oauth.invalidRequest"))}
        </p>
        <Link href="/accounts" className="text-sm text-info hover:underline">
          {t("oauth.backToApp")}
        </Link>
      </div>
    );
  }
  return (
    <ConsentForm
      data={consent.data}
      params={Object.fromEntries(searchParams.entries())}
    />
  );
}

function ConsentForm({
  data,
  params,
}: {
  data: OAuthConsentData;
  params: Record<string, string>;
}) {
  const t = useT();
  const grantable = data.accounts.filter((a) => a.can_grant);
  const [accountId, setAccountId] = useState<number | null>(
    grantable.length === 1 ? grantable[0]!.id : null,
  );
  const submit = useSubmitOAuthConsent();
  const [answer, setAnswer] = useState<"approve" | "deny" | null>(null);

  async function send(approve: boolean) {
    setAnswer(approve ? "approve" : "deny");
    try {
      const res = await submit.mutateAsync({
        ...params,
        approve,
        ...(accountId !== null ? { account_id: accountId } : {}),
      });
      window.location.assign(res.redirect_to);
    } catch {
      setAnswer(null);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex items-start gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-focused text-lit">
          <AppWindow className="h-5 w-5" aria-hidden />
        </span>
        <div className="min-w-0">
          <h1 className="text-lg font-medium leading-snug text-fg">
            {rich(t("oauth.wantsAccess"), {
              app: <span className="text-lit">{data.app.name}</span>,
            })}
          </h1>
          {data.app.owner_account_name ? (
            <p className="text-xs text-fg-muted">
              {t("oauth.createdBy")} {data.app.owner_account_name}
            </p>
          ) : null}
        </div>
      </div>

      <div className="space-y-2">
        <p className="text-sm font-medium text-fg">{t("oauth.willBeAbleTo")}</p>
        <ul className="space-y-1.5">
          {SCOPE_POINTS[data.scope].map((point) => (
            <li key={point} className="flex items-start gap-2 text-sm text-fg-muted">
              <Check className="mt-0.5 h-4 w-4 shrink-0 text-success" aria-hidden />
              {t(point)}
            </li>
          ))}
        </ul>
      </div>

      <fieldset className="space-y-2">
        <legend className="mb-2 text-sm font-medium text-fg">{t("oauth.whichAccount")}</legend>
        {data.accounts.map((account) => (
          <label
            key={account.id}
            className={cn(
              "flex items-start gap-3 rounded-control border border-glass px-3 py-2.5",
              account.can_grant
                ? "cursor-pointer hover:bg-hover-glass"
                : "cursor-not-allowed opacity-60",
              accountId === account.id && "bg-focused",
            )}
          >
            <input
              type="radio"
              name="account"
              className="mt-1"
              value={account.id}
              checked={accountId === account.id}
              disabled={!account.can_grant}
              onChange={() => setAccountId(account.id)}
            />
            <span className="min-w-0">
              <span className="block truncate text-sm text-fg">{account.name}</span>
              {account.can_grant ? null : (
                <span className="block text-xs text-fg-muted">
                  {t("oauth.roleNotAllowed")}
                </span>
              )}
            </span>
          </label>
        ))}
      </fieldset>

      <p className="text-xs text-fg-muted">
        {t("oauth.redirectNote", { host: hostOf(data.redirect_uri) })}
      </p>

      {submit.isError ? (
        <p role="alert" className="text-sm text-danger">
          {errorMessage(submit.error, t("oauth.sendFailed"))}
        </p>
      ) : null}

      <div className="flex justify-end gap-2">
        <Button
          type="button"
          variant="secondary"
          loading={answer === "deny"}
          disabled={answer !== null}
          onClick={() => void send(false)}
        >
          {t("actions.cancel")}
        </Button>
        <Button
          type="button"
          loading={answer === "approve"}
          disabled={answer !== null || accountId === null}
          onClick={() => void send(true)}
        >
          {t("oauth.authorize")}
        </Button>
      </div>
    </div>
  );
}
