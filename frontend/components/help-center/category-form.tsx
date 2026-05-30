"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { Category, CategoryInput } from "@/lib/api/portals";

export function CategoryForm({
  initial,
  submitting,
  onSubmit,
  onCancel,
}: {
  initial?: Category;
  submitting?: boolean;
  onSubmit: (input: CategoryInput) => Promise<void> | void;
  onCancel: () => void;
}) {
  const [name, setName] = useState(initial?.name ?? "");
  const [slug, setSlug] = useState(initial?.slug ?? "");
  const [locale, setLocale] = useState(initial?.locale ?? "es");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [icon, setIcon] = useState(initial?.icon ?? "");
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setError(null);
    if (!name.trim()) return setError("El nombre es obligatorio.");
    try {
      await onSubmit({
        name: name.trim(),
        slug: slug.trim() || undefined,
        locale: locale.trim() || null,
        description: description.trim() || null,
        icon: icon.trim() || null,
      });
    } catch (e) {
      setError(
        (e as { message?: string })?.message ?? "No se pudo guardar la categoría.",
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
          <Label htmlFor="c-name" required>
            Nombre
          </Label>
          <Input
            id="c-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="c-slug">Slug</Label>
          <Input
            id="c-slug"
            value={slug ?? ""}
            onChange={(e) => setSlug(e.target.value)}
            placeholder="auto-generado"
            disabled={Boolean(initial)}
          />
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="c-locale">Idioma</Label>
          <Input
            id="c-locale"
            value={locale ?? ""}
            onChange={(e) => setLocale(e.target.value)}
            placeholder="es"
            maxLength={8}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="c-icon">Icono (emoji)</Label>
          <Input
            id="c-icon"
            value={icon ?? ""}
            onChange={(e) => setIcon(e.target.value)}
            placeholder="📦"
          />
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="c-desc">Descripción</Label>
        <Textarea
          id="c-desc"
          rows={2}
          value={description ?? ""}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>

      <div className="flex gap-2">
        <Button onClick={submit} loading={submitting}>
          {initial ? "Guardar cambios" : "Crear categoría"}
        </Button>
        <Button variant="ghost" onClick={onCancel} disabled={submitting}>
          Cancelar
        </Button>
      </div>
    </div>
  );
}
