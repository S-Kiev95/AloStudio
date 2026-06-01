"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { useProfile, useUpdateProfile } from "@/lib/api/profile";

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

  // Hydrate the form when the profile loads.
  useEffect(() => {
    if (!profile.data) return;
    setName(profile.data.name ?? "");
    setDisplayName(profile.data.display_name ?? "");
    setEmail(profile.data.email ?? "");
    setSignature(profile.data.message_signature ?? "");
    const phoneAttr = profile.data.custom_attributes?.phone_number;
    setPhone(typeof phoneAttr === "string" ? phoneAttr : "");
  }, [profile.data]);

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
