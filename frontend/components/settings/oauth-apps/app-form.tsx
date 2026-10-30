"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { Textarea } from "@/components/ui/textarea";
import type { OAuthApp, OAuthAppInput } from "@/lib/api/oauth";

const KIND_OPTIONS = [
  { value: "confidential", label: "Confidencial" },
  { value: "public", label: "Pública" },
] as const;

const KIND_HINT = {
  confidential:
    "Tiene un servidor propio que guarda el secreto (una integración web, n8n, un conector).",
  public:
    "Corre en el equipo del usuario (escritorio, móvil, un script): no tiene secreto y usa PKCE.",
} as const;

/** Create (with the confidential/public choice) or edit an app. */
export function AppForm({
  initial,
  submitting,
  error,
  onSubmit,
  onCancel,
}: {
  initial?: OAuthApp;
  submitting: boolean;
  error: string | null;
  onSubmit: (input: OAuthAppInput) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [uris, setUris] = useState((initial?.redirect_uris ?? []).join("\n"));
  const [kind, setKind] = useState<"confidential" | "public">(
    initial && !initial.confidential ? "public" : "confidential",
  );

  function submit(event: React.FormEvent) {
    event.preventDefault();
    onSubmit({
      name,
      redirect_uris: uris
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean),
      confidential: kind === "confidential",
    });
  }

  return (
    <form onSubmit={submit} className="space-y-4" noValidate>
      <div className="space-y-1.5">
        <Label htmlFor="oauth-app-name" required>
          Nombre
        </Label>
        <Input
          id="oauth-app-name"
          value={name}
          maxLength={80}
          onChange={(e) => setName(e.target.value)}
          placeholder="Mi integración"
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="oauth-app-uris" required>
          URL de retorno
        </Label>
        <Textarea
          id="oauth-app-uris"
          rows={3}
          value={uris}
          onChange={(e) => setUris(e.target.value)}
          placeholder="https://tu-app.com/oauth/callback"
        />
        <p className="text-xs text-fg-muted">
          Una por línea. Tienen que empezar con https:// (o http://localhost
          para desarrollo).
        </p>
      </div>
      {initial ? null : (
        <div className="space-y-1.5">
          <p className="text-sm font-medium text-fg">Tipo</p>
          <SegmentedControl
            value={kind}
            onValueChange={setKind}
            options={KIND_OPTIONS}
            ariaLabel="Tipo de app"
          />
          <p className="text-xs text-fg-muted">{KIND_HINT[kind]}</p>
        </div>
      )}
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="ghost" size="sm" onClick={onCancel}>
          Cancelar
        </Button>
        <Button type="submit" size="sm" loading={submitting}>
          {initial ? "Guardar" : "Crear app"}
        </Button>
      </div>
    </form>
  );
}
