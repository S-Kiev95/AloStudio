"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  ARTICLE_STATUSES,
  type Article,
  type ArticleInput,
  type ArticleStatus,
  type Category,
} from "@/lib/api/portals";

const selectClass =
  "h-11 w-full rounded-md border border-border bg-surface px-3 text-sm text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

export function ArticleForm({
  categories,
  initial,
  submitting,
  onSubmit,
  onCancel,
}: {
  categories: Category[];
  initial?: Article;
  submitting?: boolean;
  onSubmit: (input: ArticleInput) => Promise<void> | void;
  onCancel: () => void;
}) {
  const [title, setTitle] = useState(initial?.title ?? "");
  const [slug, setSlug] = useState(initial?.slug ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [content, setContent] = useState(initial?.content ?? "");
  const [categoryId, setCategoryId] = useState<string>(
    initial?.category_id ? String(initial.category_id) : "",
  );
  const [locale, setLocale] = useState(initial?.locale ?? "es");
  const [status, setStatus] = useState<ArticleStatus>(
    initial?.status ?? "draft",
  );
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setError(null);
    if (!title.trim()) return setError("El título es obligatorio.");
    try {
      await onSubmit({
        title: title.trim(),
        slug: slug.trim() || undefined,
        description: description.trim() || null,
        content,
        category_id: categoryId ? Number(categoryId) : null,
        locale: locale.trim() || null,
        status,
      });
    } catch (e) {
      setError(
        (e as { message?: string })?.message ?? "No se pudo guardar el artículo.",
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

      <div className="space-y-1.5">
        <Label htmlFor="a-title" required>
          Título
        </Label>
        <Input
          id="a-title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
        />
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="a-slug">Slug</Label>
          <Input
            id="a-slug"
            value={slug ?? ""}
            onChange={(e) => setSlug(e.target.value)}
            placeholder="auto-generado"
            disabled={Boolean(initial)}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="a-locale">Idioma</Label>
          <Input
            id="a-locale"
            value={locale ?? ""}
            onChange={(e) => setLocale(e.target.value)}
            placeholder="es"
            maxLength={8}
          />
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor="a-cat">Categoría</Label>
          <select
            id="a-cat"
            className={selectClass}
            value={categoryId}
            onChange={(e) => setCategoryId(e.target.value)}
          >
            <option value="">Sin categoría</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="a-status">Estado</Label>
          <select
            id="a-status"
            className={selectClass}
            value={status}
            onChange={(e) => setStatus(e.target.value as ArticleStatus)}
          >
            {ARTICLE_STATUSES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="a-desc">Descripción corta</Label>
        <Textarea
          id="a-desc"
          rows={2}
          value={description ?? ""}
          onChange={(e) => setDescription(e.target.value)}
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="a-content">Contenido (Markdown)</Label>
        <Textarea
          id="a-content"
          rows={14}
          value={content ?? ""}
          onChange={(e) => setContent(e.target.value)}
          className="font-mono text-sm"
        />
        <p className="text-xs text-fg-muted">
          Usá Markdown estándar: ##, **negrita**, [link](url), listas con -.
        </p>
      </div>

      <div className="flex gap-2">
        <Button onClick={submit} loading={submitting}>
          {initial ? "Guardar cambios" : "Crear artículo"}
        </Button>
        <Button variant="ghost" onClick={onCancel} disabled={submitting}>
          Cancelar
        </Button>
      </div>
    </div>
  );
}
