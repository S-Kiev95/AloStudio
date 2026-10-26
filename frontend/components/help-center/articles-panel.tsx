"use client";

import {
  ChevronRight,
  Eye,
  FileText,
  Plus,
  Search,
  Trash2,
  X,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";

import { buttonVariants } from "@/components/ui/button";
import { SegmentedControl } from "@/components/ui/segmented-control";
import {
  type Article,
  type ArticleStatus,
  useArticles,
  useDeleteArticle,
} from "@/lib/api/portals";
import { cn } from "@/lib/utils";

const STATUS_FILTERS: { value: ArticleStatus | undefined; label: string }[] = [
  { value: undefined, label: "Todos" },
  { value: "published", label: "Publicados" },
  { value: "draft", label: "Borradores" },
  { value: "archived", label: "Archivados" },
];

const STATUS_BADGE: Record<ArticleStatus, string> = {
  published: "bg-success/10 text-success",
  draft: "bg-warning/10 text-warning",
  archived: "bg-surface-2 text-fg-muted",
};

const STATUS_LABEL: Record<ArticleStatus, string> = {
  published: "Publicado",
  draft: "Borrador",
  archived: "Archivado",
};

export function ArticlesPanel({
  accountId,
  slug,
  locale,
}: {
  accountId: string;
  slug: string;
  locale?: string;
}) {
  const [status, setStatus] = useState<ArticleStatus | undefined>(undefined);
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  useEffect(() => {
    const id = setTimeout(() => setDebouncedQuery(query.trim()), 300);
    return () => clearTimeout(id);
  }, [query]);

  const { data, isLoading, isError } = useArticles(accountId, slug, {
    status,
    locale,
    query: debouncedQuery || undefined,
  });

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-sm font-medium text-fg">Artículos</h3>
        <Link
          href={`/accounts/${accountId}/help-center/${slug}/articles/new`}
          className={buttonVariants({ size: "sm" })}
        >
          <Plus className="h-4 w-4" aria-hidden />
          Nuevo artículo
        </Link>
      </div>

      <div className="relative">
        <Search
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-muted"
          aria-hidden
        />
        <input
          type="search"
          aria-label="Buscar artículos"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Buscar artículos…"
          className="glass-field h-11 w-full rounded-control border border-glass bg-field pl-9 pr-9 text-sm text-fg placeholder:text-fg-muted"
        />
        {query ? (
          <button
            type="button"
            aria-label="Limpiar búsqueda"
            onClick={() => setQuery("")}
            className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1 text-fg-muted hover:bg-hover-glass hover:text-fg"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        ) : null}
      </div>

      <SegmentedControl
        ariaLabel="Estado del artículo"
        size="sm"
        value={status}
        onValueChange={setStatus}
        options={STATUS_FILTERS}
      />

      <div className="overflow-hidden rounded-md border border-glass bg-surface">
        {isLoading ? (
          <p className="p-6 text-center text-sm text-fg-muted">Cargando…</p>
        ) : isError ? (
          <p role="alert" className="p-6 text-center text-sm text-danger">
            No se pudieron cargar los artículos.
          </p>
        ) : (data?.length ?? 0) === 0 ? (
          <p className="p-6 text-center text-sm text-fg-muted">
            {debouncedQuery
              ? "No se encontraron artículos."
              : "No hay artículos todavía."}
          </p>
        ) : (
          <ul className="divide-y divide-glass">
            {data?.map((a) => (
              <ArticleRow
                key={a.id}
                accountId={accountId}
                slug={slug}
                article={a}
              />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function ArticleRow({
  accountId,
  slug,
  article,
}: {
  accountId: string;
  slug: string;
  article: Article;
}) {
  const del = useDeleteArticle(accountId, slug);
  const [error, setError] = useState<string | null>(null);

  async function onDelete(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (!window.confirm(`¿Eliminar el artículo "${article.title}"?`)) return;
    setError(null);
    try {
      await del.mutateAsync(article.id);
    } catch (err) {
      setError(
        (err as { message?: string })?.message ?? "No se pudo eliminar.",
      );
    }
  }

  return (
    <li className="flex items-center gap-1 pr-2 transition-colors hover:bg-hover-glass">
      <Link
        href={`/accounts/${accountId}/help-center/${slug}/articles/${article.id}`}
        className="flex min-w-0 flex-1 items-center gap-3 px-4 py-3 focus-visible:outline focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-neon"
      >
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-sm bg-surface-2 text-fg-muted">
          <FileText className="h-4 w-4" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-fg">{article.title}</p>
          <p className="truncate text-xs text-fg-muted">
            /{article.slug}
            {article.locale ? ` · ${article.locale}` : ""}
          </p>
          {error ? (
            <p role="alert" className="text-xs text-danger">
              {error}
            </p>
          ) : null}
        </div>
        <span className="flex items-center gap-1 font-numeric text-xs tabular-nums text-fg-muted">
          <Eye className="h-3 w-3" aria-hidden />
          {article.views}
        </span>
        <span
          className={cn(
            "rounded-pill px-2 py-0.5 text-xs font-medium",
            STATUS_BADGE[article.status],
          )}
        >
          {STATUS_LABEL[article.status]}
        </span>
      </Link>
      <button
        type="button"
        aria-label="Eliminar"
        title="Eliminar"
        onClick={onDelete}
        disabled={del.isPending}
        className="rounded-md p-1.5 text-fg-muted hover:bg-hover-glass hover:text-danger disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon"
      >
        <Trash2 className="h-4 w-4" aria-hidden />
      </button>
      <ChevronRight className="h-4 w-4 shrink-0 text-fg-muted" aria-hidden />
    </li>
  );
}
