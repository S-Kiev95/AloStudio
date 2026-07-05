"use client";

import { User as UserIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useProfile, useUpdateProfile } from "@/lib/api/profile";
import { uploadAttachment } from "@/lib/api/uploads";

export function ProfileView() {
  const profile = useProfile();
  const update = useUpdateProfile();

  const [name, setName] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [email, setEmail] = useState("");
  const [signature, setSignature] = useState("");
  const [phone, setPhone] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const [uploadingAvatar, setUploadingAvatar] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  // Avatar upload presigns against an account-scoped route; the profile
  // itself is user-level, so borrow the user's (first) account id.
  const accountId = profile.data?.account_id ?? profile.data?.accounts?.[0]?.id;

  // Hydrate the form when the profile loads.
  useEffect(() => {
    if (!profile.data) return;
    setName(profile.data.name ?? "");
    setDisplayName(profile.data.display_name ?? "");
    setEmail(profile.data.email ?? "");
    setAvatarUrl(profile.data.avatar_url ?? null);
    setSignature(profile.data.message_signature ?? "");
    const phoneAttr = profile.data.custom_attributes?.phone_number;
    setPhone(typeof phoneAttr === "string" ? phoneAttr : "");
  }, [profile.data]);

  async function onPickAvatar(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file || accountId === undefined) return;
    setError(null);
    setSaved(false);
    setUploadingAvatar(true);
    try {
      const up = await uploadAttachment(String(accountId), file);
      await update.mutateAsync({ avatar_url: up.external_url });
      setAvatarUrl(up.external_url);
      setSaved(true);
    } catch (err) {
      setError(
        (err as { message?: string })?.message ?? "No se pudo subir la foto.",
      );
    } finally {
      setUploadingAvatar(false);
    }
  }

  async function removeAvatar() {
    setError(null);
    setUploadingAvatar(true);
    try {
      await update.mutateAsync({ avatar_url: "" });
      setAvatarUrl(null);
    } catch (err) {
      setError(
        (err as { message?: string })?.message ?? "No se pudo quitar la foto.",
      );
    } finally {
      setUploadingAvatar(false);
    }
  }

  async function submit() {
    setError(null);
    setSaved(false);
    if (!name.trim()) return setError("El nombre es obligatorio.");
    try {
      await update.mutateAsync({
        name: name.trim(),
        email: email.trim() || undefined,
        display_name: displayName.trim() || null,
        message_signature: signature.trim() || null,
        phone_number: phone.trim() || null,
      });
      setSaved(true);
    } catch (e) {
      setError(
        (e as { message?: string })?.message ?? "No se pudo actualizar el perfil.",
      );
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-4 p-4 md:p-6">
      <h2 className="text-xl font-semibold text-fg">Mi perfil</h2>

      <Card>
        <CardHeader>
          <CardTitle>Datos personales</CardTitle>
        </CardHeader>
        <CardContent>
          {profile.isLoading ? (
            <p className="text-sm text-fg-muted">Cargando…</p>
          ) : profile.isError ? (
            <p role="alert" className="text-sm text-danger">
              No se pudo cargar el perfil.
            </p>
          ) : (
            <div className="space-y-4">
              {error ? (
                <p role="alert" className="text-sm text-danger">
                  {error}
                </p>
              ) : null}
              {saved ? (
                <p className="text-sm text-success">Cambios guardados.</p>
              ) : null}

              <div className="flex items-center gap-4">
                <span className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-full bg-surface-2 text-fg-muted">
                  {avatarUrl ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img
                      src={avatarUrl}
                      alt="Foto de perfil"
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    <UserIcon className="h-7 w-7" aria-hidden />
                  )}
                </span>
                <div className="flex flex-wrap gap-2">
                  <input
                    ref={fileRef}
                    type="file"
                    accept="image/*"
                    onChange={onPickAvatar}
                    className="hidden"
                    aria-label="Subir foto de perfil"
                  />
                  <Button
                    type="button"
                    variant="secondary"
                    size="sm"
                    onClick={() => fileRef.current?.click()}
                    loading={uploadingAvatar}
                    disabled={accountId === undefined}
                  >
                    Cambiar foto
                  </Button>
                  {avatarUrl ? (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={removeAvatar}
                      disabled={uploadingAvatar}
                    >
                      Quitar
                    </Button>
                  ) : null}
                </div>
              </div>

              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-1.5">
                  <Label htmlFor="p-name" required>
                    Nombre
                  </Label>
                  <Input
                    id="p-name"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                  />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="p-display">Nombre visible</Label>
                  <Input
                    id="p-display"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    placeholder={name}
                  />
                </div>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="p-email">Email</Label>
                <Input
                  id="p-email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
                <p className="text-xs text-fg-muted">
                  Al cambiar el email vas a tener que confirmar el nuevo.
                </p>
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="p-phone">Teléfono</Label>
                <Input
                  id="p-phone"
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="+598…"
                />
              </div>

              <div className="space-y-1.5">
                <Label htmlFor="p-sig">Firma de mensaje</Label>
                <Textarea
                  id="p-sig"
                  rows={3}
                  value={signature}
                  onChange={(e) => setSignature(e.target.value)}
                  placeholder="Aparece al final de tus respuestas en conversaciones."
                />
              </div>

              <div>
                <Button onClick={submit} loading={update.isPending}>
                  Guardar cambios
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
