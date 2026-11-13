"use client";

import { Camera, Globe, Mail, MapPin } from "lucide-react";
import { type FormEvent, useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
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

const VERTICALS: Array<{ value: string; label: string }> = [
  { value: "", label: "Sin elegir" },
  { value: "EDU", label: "Educación" },
  { value: "PROF_SERVICES", label: "Servicios profesionales" },
  { value: "HEALTH", label: "Salud" },
  { value: "BEAUTY", label: "Belleza, spa y salones" },
  { value: "RETAIL", label: "Tienda" },
  { value: "APPAREL", label: "Ropa" },
  { value: "GROCERY", label: "Almacén y supermercado" },
  { value: "RESTAURANT", label: "Restaurante" },
  { value: "HOTEL", label: "Hotel y alojamiento" },
  { value: "TRAVEL", label: "Viajes y transporte" },
  { value: "EVENT_PLAN", label: "Eventos" },
  { value: "ENTERTAIN", label: "Entretenimiento" },
  { value: "FINANCE", label: "Finanzas y bancos" },
  { value: "AUTO", label: "Automotor" },
  { value: "NONPROFIT", label: "Sin fines de lucro" },
  { value: "GOVT", label: "Gobierno" },
  { value: "OTHER", label: "Otro" },
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
  const vertical = VERTICALS.find((v) => v.value === draft.vertical && v.value);
  const sites = [draft.website1, draft.website2].filter((s) => s.trim());
  return (
    <div
      data-testid="whatsapp-profile-preview"
      className="overflow-hidden rounded-2xl border border-glass bg-white text-[#111b21] shadow-lg dark:bg-[#111b21] dark:text-[#e9edef]"
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
        <p className="text-xs text-[#667781] dark:text-[#8696a0]">Cuenta de empresa</p>
      </div>
      <div className="space-y-3 border-t border-[#e9edef] px-5 py-4 text-sm dark:border-[#2a3942]">
        {draft.about ? <p className="font-medium">{draft.about}</p> : null}
        {draft.description ? (
          <p className="whitespace-pre-wrap text-[#3b4a54] dark:text-[#d1d7db]">
            {draft.description}
          </p>
        ) : null}
        {vertical ? (
          <p className="text-[#667781] dark:text-[#8696a0]">{vertical.label}</p>
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

  if (profileQ.isLoading) return <p className="text-sm text-fg-muted">Consultando a Meta…</p>;
  if (profileQ.isError) {
    return (
      <p role="alert" className="text-sm text-danger">
        {(profileQ.error as Error | null)?.message ?? "No se pudo leer el perfil en Meta."}
      </p>
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
      setNotice("Perfil actualizado. Los contactos lo ven en unos minutos.");
    } catch (err) {
      setError((err as Error).message || "No se pudo guardar el perfil.");
    }
  }

  async function onPhoto(file: File | undefined) {
    if (!file) return;
    setError(null);
    setNotice(null);
    try {
      await upload.mutateAsync(file);
      setNotice("Foto actualizada.");
    } catch (err) {
      setError((err as Error).message || "No se pudo cambiar la foto.");
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
          <p className="text-sm text-fg-muted">Solo un administrador puede cambiar el perfil.</p>
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
              Cambiar foto
            </Button>
            <span className="text-xs text-fg-muted">JPG o PNG, cuadrada, hasta 5 MB.</span>
            <input
              ref={fileRef}
              type="file"
              accept="image/jpeg,image/png"
              className="hidden"
              aria-label="Foto de perfil"
              onChange={(e) => void onPhoto(e.target.files?.[0])}
            />
          </div>
        ) : null}

        <div className="space-y-1.5">
          <Label htmlFor="wa-about">Info (frase corta)</Label>
          <Input
            id="wa-about"
            value={draft.about}
            maxLength={139}
            disabled={disabled}
            onChange={(e) => set("about")(e.target.value)}
            placeholder="Ej.: Cursos y talleres en Salto"
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="wa-description">Descripción</Label>
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
            <Label htmlFor="wa-vertical">Rubro</Label>
            <select
              id="wa-vertical"
              className={selectClassName()}
              value={draft.vertical}
              disabled={disabled}
              onChange={(e) => set("vertical")(e.target.value)}
            >
              {VERTICALS.map((v) => (
                <option key={v.value} value={v.value}>
                  {v.label}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="wa-email">Correo</Label>
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
          <Label htmlFor="wa-address">Dirección</Label>
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
            <Label htmlFor="wa-web1">Sitio web</Label>
            <Input
              id="wa-web1"
              value={draft.website1}
              disabled={disabled}
              onChange={(e) => set("website1")(e.target.value)}
              placeholder="https://"
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="wa-web2">Otro sitio (opcional)</Label>
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
            Guardar perfil
          </Button>
        ) : null}
      </div>

      <div className="space-y-2 lg:sticky lg:top-4 lg:self-start">
        <p className="text-xs font-medium text-fg-muted">Vista previa: así lo ve el contacto</p>
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
