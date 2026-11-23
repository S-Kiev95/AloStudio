"use client";

import { useId } from "react";

import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import type {
  TargetSettings,
  YouTubePrivacy,
  YouTubeSettings,
} from "@/lib/api/publications";
import { useT } from "@/lib/i18n/provider";

export const YOUTUBE_TITLE_MAX = 100;

// Private until the owner picks otherwise: a video that goes out public by
// mistake can't be taken back.
export const EMPTY_YOUTUBE_SETTINGS: YouTubeSettings = {
  title: "",
  privacy_status: "private",
  made_for_kids: false,
};

const PRIVACY: YouTubePrivacy[] = ["public", "unlisted", "private"];

export function normalizeYouTubeSettings(
  raw?: TargetSettings | null,
): YouTubeSettings {
  const privacy = raw?.privacy_status;
  return {
    title: typeof raw?.title === "string" ? raw.title : "",
    privacy_status:
      privacy && PRIVACY.includes(privacy) ? privacy : "private",
    made_for_kids: Boolean(raw?.made_for_kids),
  };
}

/** The choices YouTube needs for one video: its title, who can see it and
 *  whether it is made for kids. The post's text is the description. */
export function YouTubeTargetSettings({
  value,
  onChange,
}: {
  value: YouTubeSettings;
  onChange: (patch: Partial<YouTubeSettings>) => void;
}) {
  const t = useT();
  const titleId = useId();
  const privacyId = useId();
  return (
    <div className="space-y-3">
      <div className="space-y-1">
        <label htmlFor={titleId} className="text-xs text-fg-muted">
          {t("publications.youtube.title")}
        </label>
        <Input
          id={titleId}
          value={value.title}
          maxLength={YOUTUBE_TITLE_MAX}
          placeholder={t("publications.youtube.titlePlaceholder")}
          onChange={(e) => onChange({ title: e.target.value })}
        />
      </div>
      <div className="space-y-1">
        <label htmlFor={privacyId} className="text-xs text-fg-muted">
          {t("publications.youtube.whoCanSee")}
        </label>
        <Select
          id={privacyId}
          size="sm"
          value={value.privacy_status}
          onChange={(e) =>
            onChange({ privacy_status: e.target.value as YouTubePrivacy })
          }
        >
          {PRIVACY.map((p) => (
            <option key={p} value={p}>
              {t(`publications.youtube.privacy.${p}`)}
            </option>
          ))}
        </Select>
      </div>
      <label className="flex items-center gap-2 text-sm text-fg">
        <input
          type="checkbox"
          checked={value.made_for_kids}
          onChange={(e) => onChange({ made_for_kids: e.target.checked })}
          className="accent-neon"
        />
        {t("publications.youtube.madeForKids")}
      </label>
      <p className="text-xs text-fg-muted">
        {t("publications.youtube.descriptionNote")}
      </p>
    </div>
  );
}
