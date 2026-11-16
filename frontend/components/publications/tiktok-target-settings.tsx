"use client";

import { useEffect, useRef, useState } from "react";

import {
  type Channel,
  type TargetSettings,
  type TikTokPrivacyLevel,
  type TikTokSettings,
  useChannelComposeInfo,
} from "@/lib/api/publications";
import { Select } from "@/components/ui/select";
import { useT } from "@/lib/i18n/provider";
import { rich } from "@/lib/i18n/rich";
import type { MessageKey } from "@/lib/i18n/translate";

// TikTok asks for every choice to be made by hand: nothing preselected.
export const EMPTY_TIKTOK_SETTINGS: TikTokSettings = {
  privacy_level: null,
  allow_comment: false,
  allow_duet: false,
  allow_stitch: false,
  disclose: false,
  brand_organic: false,
  brand_content: false,
};

const PRIVACY_LABELS: Record<TikTokPrivacyLevel, MessageKey> = {
  PUBLIC_TO_EVERYONE: "publications.tiktok.privacy.PUBLIC_TO_EVERYONE",
  MUTUAL_FOLLOW_FRIENDS: "publications.tiktok.privacy.MUTUAL_FOLLOW_FRIENDS",
  FOLLOWER_OF_CREATOR: "publications.tiktok.privacy.FOLLOWER_OF_CREATOR",
  SELF_ONLY: "publications.tiktok.privacy.SELF_ONLY",
};

const MUSIC_POLICY_URL =
  "https://www.tiktok.com/legal/page/global/music-usage-confirmation/en";
const BRANDED_POLICY_URL =
  "https://www.tiktok.com/legal/page/global/bc-policy/en";

function channelLabel(channel: Channel): string {
  return (
    channel.name?.trim() ||
    (channel.username ? `@${channel.username}` : "TikTok")
  );
}

export function normalizeTikTokSettings(
  raw?: TargetSettings | null,
): TikTokSettings {
  const privacy = raw?.privacy_level;
  return {
    privacy_level:
      privacy && privacy in PRIVACY_LABELS ? privacy : null,
    allow_comment: Boolean(raw?.allow_comment),
    allow_duet: Boolean(raw?.allow_duet),
    allow_stitch: Boolean(raw?.allow_stitch),
    disclose: Boolean(raw?.disclose),
    brand_organic: Boolean(raw?.brand_organic),
    brand_content: Boolean(raw?.brand_content),
  };
}

function Toggle({
  label,
  checked,
  disabled,
  title,
  onChange,
}: {
  label: string;
  checked: boolean;
  disabled?: boolean;
  title?: string;
  onChange: (next: boolean) => void;
}) {
  return (
    <label
      title={title}
      className={
        disabled
          ? "flex items-center gap-2 text-sm text-fg-muted opacity-60"
          : "flex items-center gap-2 text-sm text-fg"
      }
    >
      <input
        type="checkbox"
        checked={checked && !disabled}
        disabled={disabled}
        onChange={(e) => onChange(e.target.checked)}
        className="accent-neon"
      />
      {label}
    </label>
  );
}

/** Length in seconds of the video at ``url``, read from its metadata in
 * the browser (``null`` until known, or when there's no video). */
function useVideoDuration(url: string | null): number | null {
  const [duration, setDuration] = useState<{
    url: string;
    seconds: number;
  } | null>(null);
  useEffect(() => {
    if (!url) return;
    const video = document.createElement("video");
    video.preload = "metadata";
    video.onloadedmetadata = () => {
      if (Number.isFinite(video.duration)) {
        setDuration({ url, seconds: video.duration });
      }
    };
    video.src = url;
    return () => {
      video.onloadedmetadata = null;
      video.removeAttribute("src");
    };
  }, [url]);
  return url && duration?.url === url ? duration.seconds : null;
}

function formatMinutes(seconds: number): string {
  const whole = Math.round(seconds);
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
}

/** The options TikTok requires on its own post page: who posts, who can
 * see it, interactions and the commercial content disclosure. */
export function TikTokTargetSettings({
  accountId,
  channel,
  value,
  photosOnly,
  videoUrl,
  onChange,
  onProblemChange,
}: {
  accountId: string;
  channel: Channel;
  value: TikTokSettings;
  photosOnly: boolean;
  videoUrl: string | null;
  onChange: (patch: Partial<TikTokSettings>) => void;
  /** What keeps this target from being published that only this panel
   * knows (the video is longer than the account allows), or ``null``. */
  onProblemChange: (problem: string | null) => void;
}) {
  const t = useT();
  const info = useChannelComposeInfo(accountId, channel.id);
  const data = info.data;
  const privacyId = `tiktok-privacy-${channel.id}`;

  const duration = useVideoDuration(videoUrl);
  const maxSeconds = data?.max_video_post_duration_sec ?? null;
  const tooLong =
    duration !== null && maxSeconds !== null && duration > maxSeconds + 0.5
      ? t("publications.tiktok.tooLongProblem", {
          label: channelLabel(channel),
          duration: formatMinutes(duration),
          max: formatMinutes(maxSeconds),
        })
      : null;
  const reportProblem = useRef(onProblemChange);
  reportProblem.current = onProblemChange;
  useEffect(() => {
    reportProblem.current(tooLong);
  }, [tooLong]);
  useEffect(() => () => reportProblem.current(null), []);

  if (info.isLoading) {
    return (
      <p className="text-xs text-fg-muted">{t("publications.tiktok.checking")}</p>
    );
  }
  if (info.isError || !data || data.can_post === false) {
    return (
      <p role="alert" className="text-xs text-danger">
        {data?.message ??
          t("publications.tiktok.checkFailed")}
      </p>
    );
  }

  const maxMinutes = data.max_video_post_duration_sec
    ? Math.floor(data.max_video_post_duration_sec / 60)
    : null;

  return (
    <div className="space-y-3">
      <p className="text-xs text-fg-muted">
        {rich(t("publications.tiktok.postsTo"), {
          account: (
            <span className="font-medium text-fg">
              {data.nickname ?? channel.name}
            </span>
          ),
          username: data.username ? ` (@${data.username})` : "",
        })}
        {!photosOnly && maxMinutes
          ? ` ${t("publications.tiktok.maxMinutes", { n: maxMinutes })}`
          : ""}
      </p>
      {tooLong && duration !== null && maxSeconds !== null ? (
        <p role="alert" className="text-xs text-danger">
          {t("publications.tiktok.tooLongAlert", {
            duration: formatMinutes(duration),
            max: formatMinutes(maxSeconds),
          })}
        </p>
      ) : null}

      <div className="space-y-1">
        <label htmlFor={privacyId} className="text-xs text-fg-muted">
          {t("publications.tiktok.whoCanSee")}
        </label>
        <Select
          id={privacyId}
          size="sm"
          value={value.privacy_level ?? ""}
          onChange={(e) =>
            onChange({
              privacy_level: (e.target.value || null) as TikTokPrivacyLevel | null,
            })
          }
        >
          <option value="" disabled>
            {t("publications.tiktok.pickOption")}
          </option>
          {(data.privacy_level_options ?? []).map((level) => {
            const blocked = level === "SELF_ONLY" && value.brand_content;
            return (
              <option
                key={level}
                value={level}
                disabled={blocked}
                title={
                  blocked
                    ? t("publications.tiktok.brandNotPrivate")
                    : undefined
                }
              >
                {t(PRIVACY_LABELS[level])}
              </option>
            );
          })}
        </Select>
      </div>

      <div className="flex flex-wrap gap-x-4 gap-y-2">
        <Toggle
          label={t("publications.tiktok.allowComments")}
          checked={value.allow_comment}
          disabled={data.comment_disabled}
          title={
            data.comment_disabled
              ? t("publications.tiktok.commentsOff")
              : undefined
          }
          onChange={(next) => onChange({ allow_comment: next })}
        />
        {photosOnly ? null : (
          <>
            <Toggle
              label={t("publications.tiktok.allowDuet")}
              checked={value.allow_duet}
              disabled={data.duet_disabled}
              title={
                data.duet_disabled
                  ? t("publications.tiktok.duetOff")
                  : undefined
              }
              onChange={(next) => onChange({ allow_duet: next })}
            />
            <Toggle
              label={t("publications.tiktok.allowStitch")}
              checked={value.allow_stitch}
              disabled={data.stitch_disabled}
              title={
                data.stitch_disabled
                  ? t("publications.tiktok.stitchOff")
                  : undefined
              }
              onChange={(next) => onChange({ allow_stitch: next })}
            />
          </>
        )}
      </div>

      <div className="space-y-2">
        <Toggle
          label={t("publications.tiktok.disclose")}
          checked={value.disclose}
          onChange={(next) =>
            onChange(
              next
                ? { disclose: true }
                : { disclose: false, brand_organic: false, brand_content: false },
            )
          }
        />
        {value.disclose ? (
          <div className="space-y-2 pl-6">
            <Toggle
              label={t("publications.tiktok.yourBrand")}
              checked={value.brand_organic}
              onChange={(next) => onChange({ brand_organic: next })}
            />
            <Toggle
              label={t("publications.tiktok.brandedContent")}
              checked={value.brand_content}
              disabled={value.privacy_level === "SELF_ONLY"}
              title={
                value.privacy_level === "SELF_ONLY"
                  ? t("publications.tiktok.brandedNotSelfOnly")
                  : undefined
              }
              onChange={(next) => onChange({ brand_content: next })}
            />
            {value.brand_organic || value.brand_content ? (
              <p className="text-xs text-fg-muted">
                {value.brand_content
                  ? t("publications.tiktok.labelPaid")
                  : t("publications.tiktok.labelPromo")}
              </p>
            ) : (
              <p className="text-xs text-danger">
                {t("publications.editor.tiktokDisclosureShort")}
              </p>
            )}
          </div>
        ) : null}
      </div>

      <p className="text-xs text-fg-muted">
        {t("publications.tiktok.mayTakeMinutes")}
      </p>
    </div>
  );
}

/** The declaration TikTok asks to show right before the publish button. */
export function TikTokConsent({ settings }: { settings: TikTokSettings[] }) {
  const t = useT();
  if (settings.length === 0) return null;
  const branded = settings.some((s) => s.disclose && s.brand_content);
  const link = "text-lit underline underline-offset-2";
  return (
    <p className="text-xs text-fg-muted">
      {rich(
        t(branded ? "publications.tiktok.consentBranded" : "publications.tiktok.consent"),
        {
          brand: (
            <a href={BRANDED_POLICY_URL} target="_blank" rel="noreferrer" className={link}>
              {t("publications.tiktok.brandPolicy")}
            </a>
          ),
          music: (
            <a href={MUSIC_POLICY_URL} target="_blank" rel="noreferrer" className={link}>
              {t("publications.tiktok.musicConfirmation")}
            </a>
          ),
        },
      )}
    </p>
  );
}
