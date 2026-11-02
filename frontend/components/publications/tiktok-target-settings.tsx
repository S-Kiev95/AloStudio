"use client";

import {
  type Channel,
  type TargetSettings,
  type TikTokPrivacyLevel,
  type TikTokSettings,
  useChannelComposeInfo,
} from "@/lib/api/publications";
import { Select } from "@/components/ui/select";

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

const PRIVACY_LABELS: Record<TikTokPrivacyLevel, string> = {
  PUBLIC_TO_EVERYONE: "Todos",
  MUTUAL_FOLLOW_FRIENDS: "Amigos (se siguen mutuamente)",
  FOLLOWER_OF_CREATOR: "Seguidores",
  SELF_ONLY: "Solo yo",
};

const MUSIC_POLICY_URL =
  "https://www.tiktok.com/legal/page/global/music-usage-confirmation/en";
const BRANDED_POLICY_URL =
  "https://www.tiktok.com/legal/page/global/bc-policy/en";

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

/** The options TikTok requires on its own post page: who posts, who can
 * see it, interactions and the commercial content disclosure. */
export function TikTokTargetSettings({
  accountId,
  channel,
  value,
  photosOnly,
  onChange,
}: {
  accountId: string;
  channel: Channel;
  value: TikTokSettings;
  photosOnly: boolean;
  onChange: (patch: Partial<TikTokSettings>) => void;
}) {
  const info = useChannelComposeInfo(accountId, channel.id);
  const data = info.data;
  const privacyId = `tiktok-privacy-${channel.id}`;

  if (info.isLoading) {
    return (
      <p className="text-xs text-fg-muted">Consultando la cuenta de TikTok…</p>
    );
  }
  if (info.isError || !data || data.can_post === false) {
    return (
      <p role="alert" className="text-xs text-danger">
        {data?.message ??
          "No se pudo consultar la cuenta de TikTok. Probá de nuevo en unos minutos."}
      </p>
    );
  }

  const maxMinutes = data.max_video_post_duration_sec
    ? Math.floor(data.max_video_post_duration_sec / 60)
    : null;

  return (
    <div className="space-y-3">
      <p className="text-xs text-fg-muted">
        Se publica en la cuenta{" "}
        <span className="font-medium text-fg">
          {data.nickname ?? channel.name}
        </span>
        {data.username ? ` (@${data.username})` : ""}.
        {!photosOnly && maxMinutes
          ? ` Admite videos de hasta ${maxMinutes} minutos.`
          : ""}
      </p>

      <div className="space-y-1">
        <label htmlFor={privacyId} className="text-xs text-fg-muted">
          Quién puede verlo
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
            Elegí una opción
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
                    ? "El contenido de marca no puede tener visibilidad privada."
                    : undefined
                }
              >
                {PRIVACY_LABELS[level]}
              </option>
            );
          })}
        </Select>
      </div>

      <div className="flex flex-wrap gap-x-4 gap-y-2">
        <Toggle
          label="Permitir comentarios"
          checked={value.allow_comment}
          disabled={data.comment_disabled}
          title={
            data.comment_disabled
              ? "Los comentarios están desactivados en la configuración de la cuenta de TikTok."
              : undefined
          }
          onChange={(next) => onChange({ allow_comment: next })}
        />
        {photosOnly ? null : (
          <>
            <Toggle
              label="Permitir dúos"
              checked={value.allow_duet}
              disabled={data.duet_disabled}
              title={
                data.duet_disabled
                  ? "Los dúos están desactivados en la configuración de la cuenta de TikTok."
                  : undefined
              }
              onChange={(next) => onChange({ allow_duet: next })}
            />
            <Toggle
              label="Permitir stitch"
              checked={value.allow_stitch}
              disabled={data.stitch_disabled}
              title={
                data.stitch_disabled
                  ? "El stitch está desactivado en la configuración de la cuenta de TikTok."
                  : undefined
              }
              onChange={(next) => onChange({ allow_stitch: next })}
            />
          </>
        )}
      </div>

      <div className="space-y-2">
        <Toggle
          label="Divulgar contenido comercial"
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
              label="Tu marca"
              checked={value.brand_organic}
              onChange={(next) => onChange({ brand_organic: next })}
            />
            <Toggle
              label="Contenido de marca (con un tercero)"
              checked={value.brand_content}
              disabled={value.privacy_level === "SELF_ONLY"}
              title={
                value.privacy_level === "SELF_ONLY"
                  ? "El contenido de marca no puede tener visibilidad «Solo yo»: cambiá quién puede verlo."
                  : undefined
              }
              onChange={(next) => onChange({ brand_content: next })}
            />
            {value.brand_organic || value.brand_content ? (
              <p className="text-xs text-fg-muted">
                {value.brand_content
                  ? "La publicación se va a etiquetar como «Colaboración pagada»."
                  : "La publicación se va a etiquetar como «Contenido promocional»."}
              </p>
            ) : (
              <p className="text-xs text-danger">
                Indicá si el contenido promociona tu marca, a un tercero o ambos.
              </p>
            )}
          </div>
        ) : null}
      </div>

      <p className="text-xs text-fg-muted">
        Después de publicar, TikTok puede tardar unos minutos en mostrarla en el
        perfil.
      </p>
    </div>
  );
}

/** The declaration TikTok asks to show right before the publish button. */
export function TikTokConsent({ settings }: { settings: TikTokSettings[] }) {
  if (settings.length === 0) return null;
  const branded = settings.some((s) => s.disclose && s.brand_content);
  const link = "text-lit underline underline-offset-2";
  return (
    <p className="text-xs text-fg-muted">
      Al publicar en TikTok, aceptás{" "}
      {branded ? (
        <>
          la{" "}
          <a href={BRANDED_POLICY_URL} target="_blank" rel="noreferrer" className={link}>
            Política de contenido de marca
          </a>{" "}
          y{" "}
        </>
      ) : null}
      la{" "}
      <a href={MUSIC_POLICY_URL} target="_blank" rel="noreferrer" className={link}>
        Confirmación de uso de música
      </a>{" "}
      de TikTok.
    </p>
  );
}
