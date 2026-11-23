"use client";

import { RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useWhatsappPhoneStatus } from "@/lib/api/whatsapp-business";
import { useIntlTag, useT } from "@/lib/i18n/provider";
import type { MessageKey } from "@/lib/i18n/translate";
import { cn } from "@/lib/utils";

type Tone = "good" | "warn" | "bad" | "neutral";

const TONE_CLASS: Record<Tone, string> = {
  good: "border-success text-success",
  warn: "border-warning text-warning",
  bad: "border-danger text-danger",
  neutral: "border-glass text-fg-muted",
};

const QUALITY: Record<string, { labelKey: MessageKey; tone: Tone }> = {
  GREEN: { labelKey: "whatsapp.numberStatus.quality.high", tone: "good" },
  YELLOW: { labelKey: "whatsapp.numberStatus.quality.medium", tone: "warn" },
  RED: { labelKey: "whatsapp.numberStatus.quality.low", tone: "bad" },
};

const NAME_STATUS: Record<string, { labelKey: MessageKey; tone: Tone }> = {
  APPROVED: { labelKey: "whatsapp.numberStatus.nameStatus.approved", tone: "good" },
  AVAILABLE_WITHOUT_REVIEW: {
    labelKey: "whatsapp.numberStatus.nameStatus.approved",
    tone: "good",
  },
  PENDING_REVIEW: {
    labelKey: "whatsapp.numberStatus.nameStatus.pendingReview",
    tone: "warn",
  },
  DECLINED: { labelKey: "whatsapp.numberStatus.nameStatus.declined", tone: "bad" },
  EXPIRED: { labelKey: "whatsapp.numberStatus.nameStatus.expired", tone: "bad" },
  NONE: { labelKey: "whatsapp.numberStatus.nameStatus.none", tone: "neutral" },
};

const CONNECTION: Record<string, { labelKey: MessageKey; tone: Tone }> = {
  CONNECTED: { labelKey: "whatsapp.numberStatus.connection.connected", tone: "good" },
  PENDING: { labelKey: "whatsapp.numberStatus.connection.pending", tone: "warn" },
  MIGRATED: { labelKey: "whatsapp.numberStatus.connection.migrated", tone: "warn" },
  FLAGGED: { labelKey: "whatsapp.numberStatus.connection.flagged", tone: "warn" },
  RESTRICTED: { labelKey: "whatsapp.numberStatus.connection.restricted", tone: "bad" },
  RATE_LIMITED: { labelKey: "whatsapp.numberStatus.connection.rateLimited", tone: "bad" },
  DISCONNECTED: { labelKey: "whatsapp.numberStatus.connection.disconnected", tone: "bad" },
  OFFLINE: { labelKey: "whatsapp.numberStatus.connection.offline", tone: "bad" },
  BANNED: { labelKey: "whatsapp.numberStatus.connection.banned", tone: "bad" },
  DELETED: { labelKey: "whatsapp.numberStatus.connection.deleted", tone: "bad" },
};

/** `TIER_1K` → "1.000 contactos nuevos por día" (or translated equivalent). */
export function messagingLimitLabel(
  limit: string | null,
  opts?: {
    unlimited?: string;
    perDay?: (formattedCount: string) => string;
    localeTag?: string;
  },
): string | null {
  if (!limit) return null;
  if (/UNLIMITED/i.test(limit)) return opts?.unlimited ?? "Sin límite";
  const match = /(\d+)\s*(K)?/i.exec(limit);
  if (!match) return limit;
  const n = Number(match[1]) * (match[2] ? 1000 : 1);
  const formatted = n.toLocaleString(opts?.localeTag ?? "es-UY");
  return opts?.perDay
    ? opts.perDay(formatted)
    : `${formatted} contactos nuevos por día`;
}

function Fact({
  title,
  value,
  emptyLabel,
  tone = "neutral",
  hint,
}: {
  title: string;
  value: string | null;
  emptyLabel: string;
  tone?: Tone;
  hint: string;
}) {
  return (
    <div className="rounded-xl border border-glass bg-surface p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-fg-muted">{title}</p>
      <p
        className={cn(
          "mt-2 inline-flex rounded-pill border px-2.5 py-0.5 text-sm font-semibold",
          TONE_CLASS[value ? tone : "neutral"],
        )}
      >
        {value ?? emptyLabel}
      </p>
      <p className="mt-2 text-xs leading-snug text-fg-muted">{hint}</p>
    </div>
  );
}

/** The number's state on Meta: who it shows as, its quality and how many
 *  new conversations a day it may start. */
export function NumberStatusPanel({
  accountId,
  inboxId,
}: {
  accountId: string;
  inboxId: number;
}) {
  const t = useT();
  const intlTag = useIntlTag();
  const q = useWhatsappPhoneStatus(accountId, inboxId);

  if (q.isLoading) {
    return <p className="text-sm text-fg-muted">{t("whatsapp.common.queryingMeta")}</p>;
  }
  if (q.isError || !q.data) {
    return (
      <p role="alert" className="text-sm text-danger">
        {(q.error as Error | null)?.message ?? t("whatsapp.numberStatus.loadError")}
      </p>
    );
  }
  const s = q.data;
  const quality = QUALITY[(s.quality_rating ?? "").toUpperCase()];
  const name = NAME_STATUS[(s.name_status ?? "").toUpperCase()];
  const connection = CONNECTION[(s.status ?? "").toUpperCase()];
  const emptyLabel = t("whatsapp.common.noData");

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-lg font-semibold text-fg">
            {s.verified_name ?? t("whatsapp.common.withoutName")}
          </p>
          <p className="text-sm text-fg-muted">
            {s.display_phone_number ?? s.phone_number ?? ""}
          </p>
        </div>
        <Button
          type="button"
          variant="secondary"
          size="sm"
          loading={q.isFetching}
          onClick={() => void q.refetch()}
        >
          <RefreshCw className="h-3.5 w-3.5" aria-hidden />
          {t("whatsapp.common.refresh")}
        </Button>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Fact
          title={t("whatsapp.numberStatus.connectionTitle")}
          value={connection ? t(connection.labelKey) : s.status}
          emptyLabel={emptyLabel}
          tone={connection?.tone}
          hint={t("whatsapp.numberStatus.connectionHint")}
        />
        <Fact
          title={t("whatsapp.numberStatus.qualityTitle")}
          value={quality ? t(quality.labelKey) : s.quality_rating}
          emptyLabel={emptyLabel}
          tone={quality?.tone}
          hint={t("whatsapp.numberStatus.qualityHint")}
        />
        <Fact
          title={t("whatsapp.numberStatus.limitTitle")}
          value={messagingLimitLabel(s.messaging_limit, {
            unlimited: t("whatsapp.numberStatus.unlimited"),
            perDay: (count) => t("whatsapp.numberStatus.perDay", { count }),
            localeTag: intlTag,
          })}
          emptyLabel={emptyLabel}
          hint={t("whatsapp.numberStatus.limitHint")}
        />
        <Fact
          title={t("whatsapp.numberStatus.displayNameTitle")}
          value={name ? t(name.labelKey) : s.name_status}
          emptyLabel={emptyLabel}
          tone={name?.tone}
          hint={t("whatsapp.numberStatus.displayNameHint")}
        />
      </div>

      {quality?.tone === "bad" || connection?.tone === "bad" ? (
        <p
          role="alert"
          className="rounded-lg border border-danger px-3 py-2 text-sm text-danger"
        >
          {t("whatsapp.numberStatus.problemAlert")}
        </p>
      ) : null}
    </div>
  );
}
