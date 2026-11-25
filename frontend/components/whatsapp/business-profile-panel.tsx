"use client";

import { Camera, Globe, Mail, MapPin } from "lucide-react";
import { type FormEvent, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/error-state";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { selectClassName } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { useIsAccountAdmin } from "@/lib/api/profile";
import {
  type WhatsappBusinessProfile,
  useUpdateWhatsappProfile,
  useUploadWhatsappProfilePhoto,
  useWhatsappPhoneStatus,
  useWhatsappProfile,
} from "@/lib/api/whatsapp-business";
import { useT } from "@/lib/i18n/provider";
import type { MessageKey } from "@/lib/i18n/translate";

const VERTICALS: Array<{ value: string; labelKey: MessageKey }> = [
  { value: "", labelKey: "whatsapp.profile.verticals.none" },
  { value: "EDU", labelKey: "whatsapp.profile.verticals.EDU" },
  { value: "PROF_SERVICES", labelKey: "whatsapp.profile.verticals.PROF_SERVICES" },
  { value: "HEALTH", labelKey: "whatsapp.profile.verticals.HEALTH" },
  { value: "BEAUTY", labelKey: "whatsapp.profile.verticals.BEAUTY" },
  { value: "RETAIL", labelKey: "whatsapp.profile.verticals.RETAIL" },
  { value: "APPAREL", labelKey: "whatsapp.profile.verticals.APPAREL" },
  { value: "GROCERY", labelKey: "whatsapp.profile.verticals.GROCERY" },
  { value: "RESTAURANT", labelKey: "whatsapp.profile.verticals.RESTAURANT" },
  { value: "HOTEL", labelKey: "whatsapp.profile.verticals.HOTEL" },
  { value: "TRAVEL", labelKey: "whatsapp.profile.verticals.TRAVEL" },
  { value: "EVENT_PLAN", labelKey: "whatsapp.profile.verticals.EVENT_PLAN" },
  { value: "ENTERTAIN", labelKey: "whatsapp.profile.verticals.ENTERTAIN" },
  { value: "FINANCE", labelKey: "whatsapp.profile.verticals.FINANCE" },
  { value: "AUTO", labelKey: "whatsapp.profile.verticals.AUTO" },
  { value: "NONPROFIT", labelKey: "whatsapp.profile.verticals.NONPROFIT" },
  { value: "GOVT", labelKey: "whatsapp.profile.verticals.GOVT" },
  { value: "OTHER", labelKey: "whatsapp.profile.verticals.OTHER" },
];

type Draft = {
  about: string;
  description: string;
  address: string;
  email: string;
  website1: string;
  website2: string;
  vertical: string;
};

function toDraft(p: WhatsappBusinessProfile | undefined): Draft {
  return {
    about: p?.about ?? "",
    description: p?.description ?? "",
    address: p?.address ?? "",
    email: p?.email ?? "",
    website1: p?.websites?.[0] ?? "",
    website2: p?.websites?.[1] ?? "",
    vertical: p?.vertical && p.vertical !== "UNDEFINED" ? p.vertical : "",
  };
}

/** How the contact sees the business profile when tapping the name. */
function ProfilePreview({
  name,
  phone,
  draft,
  photoUrl,
}: {
  name: string;
  phone: string;
  draft: Draft;
  photoUrl: string | null;
}) {
  const t = useT();
  const vertical = VERTICALS.find((v) => v.value === draft.vertical && v.value);
  const sites = [draft.website1, draft.website2].filter((s) => s.trim());
  return (
    <div
      data-testid="whatsapp-profile-preview"
      className="overflow-hidden rounded-md border border-glass bg-white text-[#111b21] dark:bg-[#111b21] dark:text-[#e9edef]"
    >
      <div className="flex flex-col items-center gap-2 px-5 pb-4 pt-6">
        {photoUrl ? (
          // eslint-disable-next-line @next/next/no-img-element -- Meta's CDN, no next/image loader
          <img src={photoUrl} alt="" className="h-24 w-24 rounded-full object-cover" />
        ) : (
          <span className="flex h-24 w-24 items-center justify-center rounded-full bg-[#dfe5e7] text-3xl font-semibold text-[#54656f]">
            {name.charAt(0).toUpperCase()}
          </span>
        )}
        <p className="text-center text-xl font-medium">{name}</p>
        <p className="text-sm text-[#667781] dark:text-[#8696a0]">{phone}</p>
        <p className="text-xs text-[#667781] dark:text-[#8696a0]">
          {t("whatsapp.profile.businessAccount")}
        </p>
      </div>
      <div className="space-y-3 border-t border-[#e9edef] px-5 py-4 text-sm dark:border-[#2a3942]">
        {draft.about ? <p className="font-medium">{draft.about}</p> : null}
        {draft.description ? (
          <p className="whitespace-pre-wrap text-[#3b4a54] dark:text-[#d1d7db]">
            {draft.description}
          </p>
        ) : null}
        {vertical ? (
          <p className="text-[#667781] dark:text-[#8696a0]">{t(vertical.labelKey)}</p>
        ) : null}
        {draft.address ? (
          <p className="flex items-start gap-2">
            <MapPin className="mt-0.5 h-4 w-4 shrink-0 text-[#008069]" aria-hidden />
            {draft.address}
          </p>
        ) : null}
        {draft.email ? (
          <p className="flex items-center gap-2">
            <Mail className="h-4 w-4 shrink-0 text-[#008069]" aria-hidden />
            {draft.email}
          </p>
        ) : null}
        {sites.map((site) => (
          <p key={site} className="flex items-center gap-2 break-all">
            <Globe className="h-4 w-4 shrink-0 text-[#008069]" aria-hidden />
            {site}
          </p>
        ))}
      </div>
    </div>
  );
}

export function BusinessProfilePanel({
  accountId,
  inboxId,
  inboxName,
}: {
  accountId: string;
  inboxId: number;
  inboxName: string;
}) {
  const t = useT();
  const isAdmin = useIsAccountAdmin(accountId);
  const profileQ = useWhatsappProfile(accountId, inboxId);
  const phoneQ = useWhatsappPhoneStatus(accountId, inboxId);
  const update = useUpdateWhatsappProfile(accountId, inboxId);
  const upload = useUploadWhatsappProfilePhoto(accountId, inboxId);
  const [draft, setDraft] = useState<Draft>(() => toDraft(profileQ.data));
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (profileQ.data) setDraft(toDraft(profileQ.data));
  }, [profileQ.data]);

  if (profileQ.isLoading) {
    return <p className="text-sm text-fg-muted">{t("whatsapp.common.queryingMeta")}</p>;
  }
  if (profileQ.isError) {
    return (
      <ErrorState
        compact
        message={(profileQ.error as Error | null)?.message ?? t("whatsapp.profile.loadError")}
        onRetry={() => void profileQ.refetch()}
        retrying={profileQ.isFetching}
      />
    );
  }

  const set = (key: keyof Draft) => (value: string) =>
    setDraft((d) => ({ ...d, [key]: value }));

  async function save(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setNotice(null);
    try {
      await update.mutateAsync({
        about: draft.about,
        description: draft.description,
        address: draft.address,
        email: draft.email,
        websites: [draft.website1, draft.website2].filter((s) => s.trim()),
        vertical: draft.vertical || "UNDEFINED",
      });
      setNotice(t("whatsapp.profile.savedNotice"));
    } catch (err) {
      setError((err as Error).message || t("whatsapp.profile.saveError"));
    }
  }

  async function onPhoto(file: File | undefined) {
    if (!file) return;
    setError(null);
    setNotice(null);
    try {
      await upload.mutateAsync(file);
      setNotice(t("whatsapp.profile.photoUpdatedNotice"));
    } catch (err) {
      setError((err as Error).message || t("whatsapp.profile.photoError"));
    }
  }

  const name = phoneQ.data?.verified_name || inboxName;
  const phone = phoneQ.data?.display_phone_number ?? phoneQ.data?.phone_number ?? "";
  const disabled = !isAdmin || update.isPending;

  return (
    <form
      onSubmit={(e) => void save(e)}
      className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_340px]"
    >
      <div className="space-y-5">
        {!isAdmin ? (
          <p className="text-sm text-fg-muted">{t("whatsapp.profile.adminOnly")}</p>
        ) : null}
        {error ? (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        ) : null}
        {notice ? (
          <p role="status" className="text-sm text-success">
            {notice}
          </p>
        ) : null}

        {isAdmin ? (
          <div className="flex items-center gap-3">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              loading={upload.isPending}
              onClick={() => fileRef.current?.click()}
            >
              <Camera className="h-4 w-4" aria-hidden />
              {t("whatsapp.profile.changePhoto")}
            </Button>
            <span className="text-xs text-fg-muted">{t("whatsapp.profile.photoHint")}</span>
            <input
              ref={fileRef}
              type="file"
              accept="image/jpeg,image/png"
              className="hidden"
              aria-label={t("whatsapp.profile.photoAria")}
              onChange={(e) => void onPhoto(e.target.files?.[0])}
            />
          </div>
        ) : null}

        <div className="space-y-1.5">
          <Label htmlFor="wa-about">{t("whatsapp.profile.aboutLabel")}</Label>
          <Input
            id="wa-about"
            value={draft.about}
            maxLength={139}
            disabled={disabled}
            onChange={(e) => set("about")(e.target.value)}
            placeholder={t("whatsapp.profile.aboutPlaceholder")}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="wa-description">{t("whatsapp.profile.descriptionLabel")}</Label>
          <Textarea
            id="wa-description"
            rows={4}
            value={draft.description}
            maxLength={512}
            disabled={disabled}
            onChange={(e) => set("description")(e.target.value)}
          />
          <p className="text-right text-[11px] text-fg-muted">{draft.description.length}/512</p>
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="wa-vertical">{t("whatsapp.profile.verticalLabel")}</Label>
            <select
              id="wa-vertical"
              className={selectClassName()}
              value={draft.vertical}
              disabled={disabled}
              onChange={(e) => set("vertical")(e.target.value)}
            >
              {VERTICALS.map((v) => (
                <option key={v.value} value={v.value}>
                  {t(v.labelKey)}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="wa-email">{t("whatsapp.profile.emailLabel")}</Label>
            <Input
              id="wa-email"
              type="email"
              value={draft.email}
              maxLength={128}
              disabled={disabled}
              onChange={(e) => set("email")(e.target.value)}
            />
          </div>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="wa-address">{t("whatsapp.profile.addressLabel")}</Label>
          <Input
            id="wa-address"
            value={draft.address}
            maxLength={256}
            disabled={disabled}
            onChange={(e) => set("address")(e.target.value)}
          />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor="wa-web1">{t("whatsapp.profile.website1Label")}</Label>
            <Input
              id="wa-web1"
              value={draft.website1}
              disabled={disabled}
              onChange={(e) => set("website1")(e.target.value)}
              placeholder="https://"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="wa-web2">{t("whatsapp.profile.website2Label")}</Label>
            <Input
              id="wa-web2"
              value={draft.website2}
              disabled={disabled}
              onChange={(e) => set("website2")(e.target.value)}
              placeholder="https://"
            />
          </div>
        </div>
        {isAdmin ? (
          <Button type="submit" size="sm" loading={update.isPending}>
            {t("whatsapp.profile.saveButton")}
          </Button>
        ) : null}
      </div>

      <div className="space-y-2 lg:sticky lg:top-4 lg:self-start">
        <p className="text-xs font-medium text-fg-muted">
          {t("whatsapp.profile.previewHeading")}
        </p>
        <ProfilePreview
          name={name}
          phone={phone}
          draft={draft}
          photoUrl={profileQ.data?.profile_picture_url ?? null}
        />
      </div>
    </form>
  );
}
