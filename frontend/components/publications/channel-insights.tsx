"use client";

import { useMemo, useState } from "react";

import { SegmentedControl } from "@/components/ui/segmented-control";
import type {
  ActivityName,
  AnalyticsChannel,
  AudienceDimension,
  MetricSplit,
} from "@/lib/api/publications";
import { useIntlTag, useT } from "@/lib/i18n/provider";
import type { MessageKey } from "@/lib/i18n/translate";

import { formatDurationMs, formatMetricValue } from "./publication-detail-dialog";

/** The account's own figures (not only what was published from here),
 * shown only when the network reports them. */
const ACTIVITY_FIELDS: { key: ActivityName; label: MessageKey }[] = [
  { key: "views", label: "publications.metrics.views" },
  { key: "interactions", label: "publications.metrics.interactions" },
  { key: "accounts_engaged", label: "publications.analytics.accountsEngaged" },
  { key: "follows", label: "publications.analytics.followsGained" },
  { key: "unfollows", label: "publications.analytics.unfollows" },
  { key: "likes", label: "publications.metrics.likes" },
  { key: "comments", label: "publications.metrics.comments" },
  { key: "shares", label: "publications.metrics.shares" },
  { key: "saves", label: "publications.metrics.saves" },
  { key: "reposts", label: "publications.metrics.reposts" },
  { key: "replies", label: "publications.metrics.replies" },
  { key: "profile_links_taps", label: "publications.analytics.profileTaps" },
  { key: "watch_time_ms", label: "publications.analytics.watchTime" },
];

/** YouTube's traffic source types (insightTrafficSourceType). */
const TRAFFIC_LABELS: Record<string, MessageKey> = {
  YT_SEARCH: "publications.analytics.traffic.YT_SEARCH",
  SUGGESTED: "publications.analytics.traffic.SUGGESTED",
  RELATED_VIDEO: "publications.analytics.traffic.SUGGESTED",
  BROWSE: "publications.analytics.traffic.BROWSE",
  SUBSCRIBER: "publications.analytics.traffic.BROWSE",
  EXT_URL: "publications.analytics.traffic.EXT_URL",
  YT_CHANNEL: "publications.analytics.traffic.YT_CHANNEL",
  PLAYLIST: "publications.analytics.traffic.PLAYLIST",
  NOTIFICATION: "publications.analytics.traffic.NOTIFICATION",
  SHORTS: "publications.analytics.traffic.SHORTS",
  END_SCREEN: "publications.analytics.traffic.END_SCREEN",
  HASHTAGS: "publications.analytics.traffic.HASHTAGS",
  ADVERTISING: "publications.analytics.traffic.ADVERTISING",
  NO_LINK_OTHER: "publications.analytics.traffic.NO_LINK_OTHER",
  YT_OTHER_PAGE: "publications.analytics.traffic.YT_OTHER_PAGE",
};

const SURFACE_LABELS: Record<string, MessageKey> = {
  reels: "publications.analytics.surfaceReels",
  stories: "publications.analytics.surfaceStories",
  posts: "publications.analytics.surfacePosts",
  ads: "publications.analytics.surfaceAds",
};

const BUTTON_LABELS: Record<string, MessageKey> = {
  call: "publications.analytics.buttonCall",
  email: "publications.analytics.buttonEmail",
  directions: "publications.analytics.buttonDirections",
  message: "publications.analytics.buttonMessage",
  book: "publications.analytics.buttonBook",
};

const GENDER_LABELS: Record<string, MessageKey> = {
  F: "publications.analytics.genderF",
  M: "publications.analytics.genderM",
  U: "publications.analytics.genderU",
};

const DIMENSIONS: { value: AudienceDimension; label: MessageKey }[] = [
  { value: "country", label: "publications.analytics.country" },
  { value: "city", label: "publications.analytics.city" },
  { value: "age", label: "publications.analytics.age" },
  { value: "gender", label: "publications.analytics.gender" },
];

type Who = "followers" | "engaged";

export function ChannelInsights({ entry }: { entry: AnalyticsChannel }) {
  const t = useT();
  const intlTag = useIntlTag();
  const activity = ACTIVITY_FIELDS.filter(
    (f) => typeof entry.activity?.[f.key] === "number",
  );
  const surfaces = entry.breakdowns?.views_by_surface;
  const buttons = entry.breakdowns?.profile_taps_by_button;
  const traffic = entry.breakdowns?.views_by_traffic_source;
  const hasSplits = Boolean(
    (surfaces && Object.keys(surfaces).length) ||
      (buttons && Object.keys(buttons).length) ||
      (traffic && Object.keys(traffic).length),
  );

  if (!activity.length && !hasSplits && !entry.audience) {
    return null;
  }

  return (
    <div className="space-y-4 border-t border-glass pt-3">
      {activity.length ? (
        <section className="space-y-2" aria-label={t("publications.analytics.activity")}>
          <div>
            <p className="text-xs font-medium text-fg-muted">
              {t("publications.analytics.activity")}
            </p>
            <p className="text-[11px] text-fg-muted">
              {t("publications.analytics.activityHint")}
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-6">
            {activity.map((f) => (
              <div
                key={f.key}
                className="rounded-sm border border-glass bg-surface-2 px-3 py-2"
              >
                <p className="text-[10px] uppercase tracking-wide text-fg-muted">
                  {t(f.label)}
                </p>
                <p className="font-numeric text-sm font-semibold tabular-nums text-fg">
                  {f.key === "watch_time_ms"
                    ? formatDurationMs(entry.activity?.[f.key] ?? 0, intlTag)
                    : formatMetricValue(entry.activity?.[f.key], intlTag)}
                </p>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {hasSplits ? (
        <div className="grid gap-4 md:grid-cols-2">
          {surfaces && Object.keys(surfaces).length ? (
            <SplitBars
              title={t("publications.analytics.viewsBySurface")}
              split={surfaces}
              label={(k) => (SURFACE_LABELS[k] ? t(SURFACE_LABELS[k]) : k)}
            />
          ) : null}
          {traffic && Object.keys(traffic).length ? (
            <SplitBars
              title={t("publications.analytics.viewsByTrafficSource")}
              split={traffic}
              label={(k) => (TRAFFIC_LABELS[k] ? t(TRAFFIC_LABELS[k]) : k)}
            />
          ) : null}
          {buttons && Object.keys(buttons).length ? (
            <SplitBars
              title={t("publications.analytics.tapsByButton")}
              split={buttons}
              label={(k) => (BUTTON_LABELS[k] ? t(BUTTON_LABELS[k]) : k)}
            />
          ) : null}
        </div>
      ) : null}

      {entry.audience !== undefined ? <AudiencePanel entry={entry} /> : null}
    </div>
  );
}

function SplitBars({
  title,
  split,
  label,
}: {
  title: string;
  split: MetricSplit;
  label: (key: string) => string;
}) {
  const intlTag = useIntlTag();
  const rows = Object.entries(split).sort((a, b) => b[1] - a[1]);
  const total = rows.reduce((sum, [, v]) => sum + v, 0) || 1;
  return (
    <section className="space-y-2" aria-label={title}>
      <p className="text-xs font-medium text-fg-muted">{title}</p>
      <ul className="space-y-1.5">
        {rows.map(([key, value]) => {
          const pct = Math.round((value / total) * 100);
          return (
            <li key={key} className="space-y-0.5">
              <div className="flex items-baseline justify-between gap-2 text-xs">
                <span className="truncate text-fg">{label(key)}</span>
                <span className="font-numeric tabular-nums text-fg-muted">
                  {value.toLocaleString(intlTag)} · {pct}%
                </span>
              </div>
              <div className="h-1.5 overflow-hidden rounded-full bg-surface-2">
                <div
                  className="h-full rounded-full bg-neon"
                  style={{ width: `${pct}%` }}
                />
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function AudiencePanel({ entry }: { entry: AnalyticsChannel }) {
  const t = useT();
  const intlTag = useIntlTag();
  const audience = entry.audience ?? {};
  const available = (["followers", "engaged"] as Who[]).filter(
    (w) => audience[w] && Object.keys(audience[w] ?? {}).length,
  );
  const [who, setWho] = useState<Who>("followers");
  const [dimension, setDimension] = useState<AudienceDimension>("country");
  const shownWho = available.includes(who) ? who : available[0];
  const split = shownWho ? audience[shownWho]?.[dimension] : undefined;

  const regionNames = useMemo(() => {
    try {
      return new Intl.DisplayNames([intlTag], { type: "region" });
    } catch {
      return null;
    }
  }, [intlTag]);

  const label = (key: string): string => {
    if (dimension === "country") {
      try {
        return regionNames?.of(key) ?? key;
      } catch {
        return key;
      }
    }
    if (dimension === "gender") {
      return GENDER_LABELS[key] ? t(GENDER_LABELS[key]) : key;
    }
    return key;
  };

  return (
    <section className="space-y-2" aria-label={t("publications.analytics.audience")}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-xs font-medium text-fg-muted">
          {t("publications.analytics.audience")}
        </p>
        {available.length > 1 ? (
          <SegmentedControl
            ariaLabel={t("publications.analytics.audience")}
            size="sm"
            value={shownWho}
            onValueChange={setWho}
            options={[
              { value: "followers" as Who, label: t("publications.analytics.audienceFollowers") },
              { value: "engaged" as Who, label: t("publications.analytics.audienceEngaged") },
            ]}
          />
        ) : null}
      </div>

      {!available.length ? (
        <p className="text-xs text-fg-muted">{t("publications.analytics.audienceEmpty")}</p>
      ) : (
        <>
          <SegmentedControl
            ariaLabel={t("publications.analytics.audience")}
            size="sm"
            value={dimension}
            onValueChange={setDimension}
            options={DIMENSIONS.map((d) => ({ value: d.value, label: t(d.label) }))}
          />
          {split && Object.keys(split).length ? (
            <SplitBars title={t(DIMENSIONS.find((d) => d.value === dimension)!.label)} split={split} label={label} />
          ) : (
            <p className="text-xs text-fg-muted">{t("publications.analytics.audienceEmpty")}</p>
          )}
        </>
      )}
    </section>
  );
}
