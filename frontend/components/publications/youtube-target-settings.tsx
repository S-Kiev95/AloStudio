"use client";

import { X } from "lucide-react";
import { useId, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useMediaAssets } from "@/lib/api/media";
import {
  type Channel,
  type TargetSettings,
  useChannelComposeInfo,
  type YouTubePrivacy,
  type YouTubeSettings,
} from "@/lib/api/publications";
import { useT } from "@/lib/i18n/provider";

export const YOUTUBE_TITLE_MAX = 100;
export const YOUTUBE_TAGS_MAX = 500;
export const YOUTUBE_DEFAULT_CATEGORY = "22";

// Private until the owner picks otherwise: a video that goes out public by
// mistake can't be taken back.
export const EMPTY_YOUTUBE_SETTINGS: YouTubeSettings = {
  title: "",
  privacy_status: "private",
  made_for_kids: false,
  tags: [],
  category_id: YOUTUBE_DEFAULT_CATEGORY,
  playlist_id: null,
  thumbnail_media_id: null,
};

const PRIVACY: YouTubePrivacy[] = ["public", "unlisted", "private"];

/** How YouTube counts the 500 characters of the tags (the backend's
 *  ``tags_length``): characters, a comma between each, and quotes around a
 *  tag with spaces. */
export function youtubeTagsLength(tags: string[]): number {
  if (tags.length === 0) return 0;
  return (
    tags.reduce((sum, tag) => sum + Array.from(tag).length + (tag.includes(" ") ? 2 : 0), 0) +
    tags.length -
    1
  );
}

export function normalizeYouTubeSettings(
  raw?: TargetSettings | null,
): YouTubeSettings {
  const privacy = raw?.privacy_status;
  return {
    title: typeof raw?.title === "string" ? raw.title : "",
    privacy_status:
      privacy && PRIVACY.includes(privacy) ? privacy : "private",
    made_for_kids: Boolean(raw?.made_for_kids),
    tags: Array.isArray(raw?.tags) ? raw.tags.filter((t) => typeof t === "string") : [],
    category_id:
      typeof raw?.category_id === "string" && raw.category_id
        ? raw.category_id
        : YOUTUBE_DEFAULT_CATEGORY,
    playlist_id: typeof raw?.playlist_id === "string" ? raw.playlist_id : null,
    thumbnail_media_id:
      typeof raw?.thumbnail_media_id === "number" ? raw.thumbnail_media_id : null,
  };
}

function ThumbnailPicker({
  accountId,
  value,
  onChange,
}: {
  accountId: string;
  value: number | null;
  onChange: (id: number | null) => void;
}) {
  const t = useT();
  const [open, setOpen] = useState(false);
  const images = useMediaAssets(accountId, { kind: "image" });
  const assets = images.data ?? [];
  const chosen = assets.find((a) => a.id === value) ?? null;

  return (
    <div className="space-y-1.5">
      <p className="text-xs text-fg-muted">{t("publications.youtube.thumbnail")}</p>
      <div className="flex flex-wrap items-center gap-2">
        {value !== null ? (
          <div className="flex items-center gap-2 rounded-sm border border-glass bg-field p-1.5">
            {chosen ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={chosen.url} alt="" className="h-10 w-16 rounded-sm object-cover" />
            ) : null}
            <span className="max-w-40 truncate text-xs text-fg">
              {chosen?.filename ?? `#${value}`}
            </span>
            <button
              type="button"
              aria-label={t("publications.youtube.removeThumbnail")}
              className="rounded-sm p-1 text-fg-muted hover:bg-hover-glass hover:text-fg"
              onClick={() => onChange(null)}
            >
              <X className="h-3.5 w-3.5" aria-hidden />
            </button>
          </div>
        ) : null}
        <Button type="button" size="sm" variant="secondary" onClick={() => setOpen((o) => !o)}>
          {t("publications.youtube.chooseThumbnail")}
        </Button>
      </div>
      {open ? (
        assets.length === 0 ? (
          <p className="text-xs text-fg-muted">{t("publications.youtube.noImages")}</p>
        ) : (
          <ul className="grid grid-cols-4 gap-1.5 sm:grid-cols-6">
            {assets.map((asset) => (
              <li key={asset.id}>
                <button
                  type="button"
                  aria-label={asset.filename ?? `#${asset.id}`}
                  aria-pressed={asset.id === value}
                  className="block w-full overflow-hidden rounded-sm border border-glass hover:border-border-strong aria-pressed:ring-2 aria-pressed:ring-neon"
                  onClick={() => {
                    onChange(asset.id);
                    setOpen(false);
                  }}
                >
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img src={asset.url} alt="" className="aspect-video w-full object-cover" />
                </button>
              </li>
            ))}
          </ul>
        )
      ) : null}
      <p className="text-[11px] text-fg-muted">{t("publications.youtube.thumbnailHelp")}</p>
    </div>
  );
}

function TagsInput({
  value,
  onChange,
}: {
  value: string[];
  onChange: (tags: string[]) => void;
}) {
  const t = useT();
  const id = useId();
  const [draft, setDraft] = useState("");
  const length = youtubeTagsLength(value);

  function commit(text: string) {
    const fresh = text
      .split(",")
      .map((s) => s.replace(/[<>]/g, "").trim())
      .filter((s) => s && !value.includes(s));
    if (fresh.length) onChange([...value, ...fresh]);
    setDraft("");
  }

  return (
    <div className="space-y-1">
      <label htmlFor={id} className="text-xs text-fg-muted">
        {t("publications.youtube.tags")}
      </label>
      {value.length > 0 ? (
        <ul className="flex flex-wrap gap-1">
          {value.map((tag) => (
            <li
              key={tag}
              className="inline-flex items-center gap-1 rounded-sm border border-glass bg-field px-1.5 py-0.5 text-xs text-fg"
            >
              {tag}
              <button
                type="button"
                aria-label={t("publications.youtube.removeTag", { tag })}
                className="text-fg-muted hover:text-fg"
                onClick={() => onChange(value.filter((x) => x !== tag))}
              >
                <X className="h-3 w-3" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      <Input
        id={id}
        value={draft}
        placeholder={t("publications.youtube.tagsPlaceholder")}
        onChange={(e) => {
          const next = e.target.value;
          if (next.includes(",")) commit(next);
          else setDraft(next);
        }}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            commit(draft);
          }
        }}
        onBlur={() => commit(draft)}
      />
      <p
        className={
          length > YOUTUBE_TAGS_MAX ? "text-[11px] text-danger" : "text-[11px] text-fg-muted"
        }
      >
        {t("publications.youtube.tagsCount", { count: length, max: YOUTUBE_TAGS_MAX })}
      </p>
    </div>
  );
}

/** The choices YouTube needs for one video: title, who can see it, made for
 *  kids, tags, category, playlist and thumbnail. The post's text is the
 *  description. */
export function YouTubeTargetSettings({
  accountId,
  channel,
  value,
  onChange,
}: {
  accountId: string;
  channel: Channel;
  value: YouTubeSettings;
  onChange: (patch: Partial<YouTubeSettings>) => void;
}) {
  const t = useT();
  const titleId = useId();
  const privacyId = useId();
  const categoryId = useId();
  const playlistId = useId();
  const info = useChannelComposeInfo(accountId, channel.id);
  const categories = info.data?.categories ?? [];
  const playlists = info.data?.playlists ?? [];
  const category = value.category_id ?? YOUTUBE_DEFAULT_CATEGORY;

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
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1">
          <label htmlFor={privacyId} className="text-xs text-fg-muted">
            {t("publications.youtube.whoCanSee")}
          </label>
          <Select
            id={privacyId}
            size="sm"
            className="w-full"
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
        <div className="space-y-1">
          <label htmlFor={categoryId} className="text-xs text-fg-muted">
            {t("publications.youtube.category")}
          </label>
          <Select
            id={categoryId}
            size="sm"
            className="w-full"
            value={category}
            onChange={(e) => onChange({ category_id: e.target.value })}
          >
            {categories.some((c) => c.id === category) ? null : (
              <option value={category}>{t("publications.youtube.categoryDefault")}</option>
            )}
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.title}
              </option>
            ))}
          </Select>
        </div>
      </div>
      <div className="space-y-1">
        <label htmlFor={playlistId} className="text-xs text-fg-muted">
          {t("publications.youtube.playlist")}
        </label>
        <Select
          id={playlistId}
          size="sm"
          className="w-full"
          value={value.playlist_id ?? ""}
          onChange={(e) => onChange({ playlist_id: e.target.value || null })}
        >
          <option value="">{t("publications.youtube.noPlaylist")}</option>
          {playlists.map((p) => (
            <option key={p.id} value={p.id}>
              {p.title}
            </option>
          ))}
        </Select>
      </div>
      <TagsInput value={value.tags ?? []} onChange={(tags) => onChange({ tags })} />
      <ThumbnailPicker
        accountId={accountId}
        value={value.thumbnail_media_id ?? null}
        onChange={(thumbnail_media_id) => onChange({ thumbnail_media_id })}
      />
      <label className="flex items-center gap-2 text-sm text-fg">
        <input
          type="checkbox"
          checked={value.made_for_kids}
          onChange={(e) => onChange({ made_for_kids: e.target.checked })}
          className="accent-neon"
        />
        {t("publications.youtube.madeForKids")}
      </label>
      {info.data?.message ? (
        <p className="text-xs text-warning">{info.data.message}</p>
      ) : null}
      <p className="text-xs text-fg-muted">
        {t("publications.youtube.descriptionNote")}
      </p>
    </div>
  );
}
