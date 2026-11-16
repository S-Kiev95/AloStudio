"use client";

import { Image as ImageIcon } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { Portal, PortalInput } from "@/lib/api/portals";
import { uploadAttachment } from "@/lib/api/uploads";
import { useT } from "@/lib/i18n/provider";

export function PortalForm({
  accountId,
  initial,
  submitting,
  onSubmit,
  onCancel,
}: {
  accountId: string;
  initial?: Portal;
  submitting?: boolean;
  onSubmit: (input: PortalInput) => Promise<void> | void;
  onCancel: () => void;
}) {
  const t = useT();
  const [name, setName] = useState(initial?.name ?? "");
  const [slug, setSlug] = useState(initial?.slug ?? "");
  const [color, setColor] = useState(initial?.color ?? "#1f93ff");
  const [customDomain, setCustomDomain] = useState(initial?.custom_domain ?? "");
  const [homepageLink, setHomepageLink] = useState(initial?.homepage_link ?? "");
  const [pageTitle, setPageTitle] = useState(initial?.page_title ?? "");
  const [headerText, setHeaderText] = useState(initial?.header_text ?? "");
  const [archived, setArchived] = useState(initial?.archived ?? false);
  const [logo, setLogo] = useState(initial?.logo ?? "");
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const logoRef = useRef<HTMLInputElement>(null);
  const [error, setError] = useState<string | null>(null);

  async function onPickLogo(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setError(null);
    setUploadingLogo(true);
    try {
      const up = await uploadAttachment(accountId, file);
      setLogo(up.external_url);
    } catch (err) {
      setError(
        (err as { message?: string })?.message ?? t("helpCenter.logoUploadFailed"),
      );
    } finally {
      setUploadingLogo(false);
    }
  }

  async function submit() {
    setError(null);
    if (!name.trim()) return setError(t("products.form.nameRequired"));
    try {
      await onSubmit({
        name: name.trim(),
        slug: slug.trim() || undefined,
        color: color.trim() || null,
        custom_domain: customDomain.trim() || null,
        homepage_link: homepageLink.trim() || null,
        page_title: pageTitle.trim() || null,
        header_text: headerText.trim() || null,
        logo: logo.trim() || null,
        archived,
      });
    } catch (e) {
      setError(
        (e as { message?: string })?.message ?? t("helpCenter.portalSaveFailed"),
      );
    }
  }

  return (
    <div className="space-y-4">
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="p-name" required>
            {t("profile.name")}
          </Label>
          <Input
            id="p-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={255}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="p-slug">Slug</Label>
          <Input
            id="p-slug"
            value={slug ?? ""}
            onChange={(e) => setSlug(e.target.value)}
            placeholder="auto-generado a partir del nombre"
            disabled={Boolean(initial)}
          />
          {initial ? (
            <p className="text-xs text-fg-muted">
              {t("helpCenter.slugLocked")}
            </p>
          ) : null}
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="space-y-1.5">
          <Label htmlFor="p-color">{t("helpCenter.color")}</Label>
          <div className="flex items-center gap-2">
            <input
              id="p-color"
              type="color"
              value={color ?? "#1f93ff"}
              onChange={(e) => setColor(e.target.value)}
              className="h-11 w-14 cursor-pointer rounded-md border border-border bg-surface"
            />
            <Input
              value={color ?? ""}
              onChange={(e) => setColor(e.target.value)}
              placeholder="#1f93ff"
            />
          </div>
        </div>
        <div className="space-y-1.5 sm:col-span-2">
          <Label htmlFor="p-domain">{t("helpCenter.customDomain")}</Label>
          <Input
            id="p-domain"
            value={customDomain ?? ""}
            onChange={(e) => setCustomDomain(e.target.value)}
            placeholder="ayuda.midominio.com"
          />
        </div>
      </div>

      <div className="space-y-1.5">
        <Label>Logo</Label>
        <div className="flex items-center gap-4">
          <span className="flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-md border border-border bg-surface-2 text-fg-muted">
            {logo ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={logo}
                alt={t("helpCenter.portalLogo")}
                className="h-full w-full object-cover"
              />
            ) : (
              <ImageIcon className="h-6 w-6" aria-hidden />
            )}
          </span>
          <div className="flex flex-wrap gap-2">
            <input
              ref={logoRef}
              type="file"
              accept="image/*"
              onChange={onPickLogo}
              className="hidden"
              aria-label={t("helpCenter.uploadLogo")}
            />
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => logoRef.current?.click()}
              loading={uploadingLogo}
            >
              {t("helpCenter.uploadLogo")}
            </Button>
            {logo ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setLogo("")}
                disabled={uploadingLogo}
              >
                {t("common.remove")}
              </Button>
            ) : null}
          </div>
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="p-home">{t("helpCenter.homepageLink")}</Label>
        <Input
          id="p-home"
          type="url"
          value={homepageLink ?? ""}
          onChange={(e) => setHomepageLink(e.target.value)}
          placeholder="https://midominio.com"
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="p-title">{t("helpCenter.pageTitle")}</Label>
        <Input
          id="p-title"
          value={pageTitle ?? ""}
          onChange={(e) => setPageTitle(e.target.value)}
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="p-header">{t("helpCenter.headerText")}</Label>
        <Textarea
          id="p-header"
          rows={2}
          value={headerText ?? ""}
          onChange={(e) => setHeaderText(e.target.value)}
        />
      </div>

      <label className="flex items-center gap-2 text-sm text-fg">
        <input
          type="checkbox"
          checked={archived}
          onChange={(e) => setArchived(e.target.checked)}
        />
        {t("helpCenter.archivedHidden")}
      </label>

      <div className="flex gap-2">
        <Button onClick={submit} loading={submitting}>
          {initial ? t("common.saveChanges") : t("helpCenter.createPortal")}
        </Button>
        <Button variant="ghost" onClick={onCancel} disabled={submitting}>
          {t("actions.cancel")}
        </Button>
      </div>
    </div>
  );
}
