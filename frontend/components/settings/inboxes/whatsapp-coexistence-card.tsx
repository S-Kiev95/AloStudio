"use client";

import { AlertTriangle, Smartphone } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { WhatsappCoexistence } from "@/lib/api/inboxes";
import { useIntlTag, useT } from "@/lib/i18n/provider";
import type { MessageKey } from "@/lib/i18n/translate";

/** Meta's ``disconnection_info.reason`` → what happened, in words. */
const REASONS: Record<string, MessageKey> = {
  PRIMARY_INACTIVITY: "settingsInboxes.coexistence.reasonPrimaryInactivity",
  COMPANION_INACTIVITY: "settingsInboxes.coexistence.reasonCompanionInactivity",
  CHANGE_NUMBER: "settingsInboxes.coexistence.reasonChangeNumber",
  USER_RE_REGISTERED: "settingsInboxes.coexistence.reasonReRegistered",
  BUSINESS_DOWNGRADE: "settingsInboxes.coexistence.reasonDowngrade",
  ACCOUNT_DISCONNECTED: "settingsInboxes.coexistence.reasonAccountDisconnected",
};

function reasonKey(state: NonNullable<WhatsappCoexistence["disconnected"]>): MessageKey {
  if (state.reason && REASONS[state.reason]) return REASONS[state.reason];
  if (state.initiated_by === "USER") return "settingsInboxes.coexistence.reasonUser";
  return "settingsInboxes.coexistence.reasonOther";
}

export function WhatsappCoexistenceCard({ state }: { state: WhatsappCoexistence }) {
  const t = useT();
  const intlTag = useIntlTag();
  const off = state.disconnected;

  const stateText = (value: string | null, progress?: number | null): string | null => {
    switch (value) {
      case "requested":
        return t("settingsInboxes.coexistence.stateRequested");
      case "importing":
        return t("settingsInboxes.coexistence.stateImporting", {
          progress: String(progress ?? 0),
        });
      case "done":
        return t("settingsInboxes.coexistence.stateDone");
      case "declined":
        return t("settingsInboxes.coexistence.stateDeclined");
      case "failed":
        return t("settingsInboxes.coexistence.stateFailed");
      default:
        return null;
    }
  };
  const rows: { label: MessageKey; text: string | null }[] = [
    { label: "settingsInboxes.coexistence.contacts", text: stateText(state.contacts) },
    { label: "settingsInboxes.coexistence.history", text: stateText(state.history, state.progress) },
  ];
  const arriving = state.history === "requested" || state.history === "importing";
  const since = off?.at ? new Date(off.at) : null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Smartphone className="h-4 w-4" aria-hidden />
          {t("settingsInboxes.coexistence.title")}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {off ? (
          <div
            role="alert"
            className="space-y-1 rounded-control border border-danger bg-surface-2 px-3 py-2"
          >
            <p className="flex items-center gap-1.5 text-sm font-medium text-danger">
              <AlertTriangle className="h-4 w-4" aria-hidden />
              {t("settingsInboxes.coexistence.disconnectedTitle")}
            </p>
            <p className="text-sm text-fg">{t(reasonKey(off))}</p>
            {since && !Number.isNaN(since.getTime()) ? (
              <p className="text-xs text-fg-muted">
                {t("settingsInboxes.coexistence.since", {
                  date: since.toLocaleString(intlTag, { dateStyle: "medium", timeStyle: "short" }),
                })}
              </p>
            ) : null}
            <p className="text-xs text-fg-muted">
              {t("settingsInboxes.coexistence.disconnectedBody")}
            </p>
          </div>
        ) : null}

        <p className="text-sm text-fg-muted">{t("settingsInboxes.coexistence.intro")}</p>

        <dl className="space-y-2">
          {rows
            .filter((r) => r.text)
            .map((r) => (
              <div key={r.label} className="flex flex-wrap items-baseline justify-between gap-2">
                <dt className="text-sm text-fg">{t(r.label)}</dt>
                <dd className="text-sm text-fg-muted">{r.text}</dd>
              </div>
            ))}
        </dl>

        {state.history === "importing" && typeof state.progress === "number" ? (
          <div
            role="progressbar"
            aria-label={t("settingsInboxes.coexistence.history")}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={state.progress}
            className="h-1.5 overflow-hidden rounded-full bg-surface-2"
          >
            <div
              className="h-full rounded-full bg-neon"
              style={{ width: `${Math.min(100, Math.max(0, state.progress))}%` }}
            />
          </div>
        ) : null}

        {arriving && !off ? (
          <p className="text-xs text-fg-muted">{t("settingsInboxes.coexistence.keepOpen")}</p>
        ) : null}
      </CardContent>
    </Card>
  );
}
