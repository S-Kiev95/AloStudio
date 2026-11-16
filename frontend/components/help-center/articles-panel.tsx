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
import { useT } from "@/lib/i18n/provider";
import type { MessageKey } from "@/lib/i18n/translate";

const STATUS_FILTERS: { value: ArticleStatus | undefined; label: MessageKey }[] = [
  { value: undefined, label: "helpCenter.filters.all" },
  { value: "published", label: "helpCenter.filters.published" },
  { value: "draft", label: "helpCenter.filters.drafts" },
  { value: "archived", label: "helpCenter.filters.archived" },
];

const STATUS_BADGE: Record<ArticleStatus, string> = {
  published: "bg-success/10 text-success",
  draft: "bg-warning/10 text-warning",
  archived: "bg-surface-2 text-fg-muted",
};

const STATUS_LABEL: Record<ArticleStatus, MessageKey> = {
  published: "helpCenter.status.published",
  draft: "helpCenter.status.draft",
  archived: "helpCenter.status.archived",
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
  const t = useT();
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
        <h3 className="text-sm font-medium text-fg">{t("helpCenter.articles")}</h3>
        <Link
          href={`/accounts/${accountId}/help-center/${slug}/articles/new`}
          className={buttonVariants({ size: "sm" })}
        >
          <Plus className="h-4 w-4" aria-hidden />
          {t("helpCenter.newArticle")}
        </Link>
      </div>

      <div className="relative">
        <Search
          className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-muted"
          aria-hidden
        />
        <input
          type="search"
          aria-label={t("helpCenter.searchArticles")}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder={t("helpCenter.searchArticlesPlaceholder")}
          className="glass-field h-11 w-full rounded-control border border-glass bg-field pl-9 pr-9 text-sm text-fg placeholder:text-fg-muted"
        />
        {query ? (
          <button
            type="button"
            aria-label={t("conversations.list.clearSearch")}
            onClick={() => setQuery("")}
            className="absolute right-2 top-1/2 -translate-y-1/2 rounded-md p-1 text-fg-muted hover:bg-hover-glass hover:text-fg"
          >
            <X className="h-4 w-4" aria-hidden />
          </button>
        ) : null}
      </div>

      <SegmentedControl
        ariaLabel={t("helpCenter.articleStatus")}
        size="sm"
        value={status}
        onValueChange={setStatus}
        options={STATUS_FILTERS.map((o) => ({ ...o, label: t(o.label) }))}
      />

      <div className="overflow-hidden rounded-md border border-glass bg-surface">
        {isLoading ? (
          <p className="p-6 text-center text-sm text-fg-muted">{t("common.loading")}</p>
        ) : isError ? (
          <p role="alert" className="p-6 text-center text-sm text-danger">
            {t("helpCenter.articlesLoadFailed")}
          </p>
        ) : (data?.length ?? 0) === 0 ? (
          <p className="p-6 text-center text-sm text-fg-muted">
            {debouncedQuery
              ? t("helpCenter.noArticlesFound")
              : t("helpCenter.noArticles")}
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
  const t = useT();
  const del = useDeleteArticle(accountId, slug);
  const [error, setError] = useState<string | null>(null);

  async function onDelete(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (!window.confirm(t("helpCenter.deleteArticleConfirm", { title: article.title }))) return;
    setError(null);
    try {
      await del.mutateAsync(article.id);
    } catch (err) {
      setError(
        (err as { message?: string })?.message ?? t("actions.deleteFailed"),
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
          {t(STATUS_LABEL[article.status])}
        </span>
      </Link>
      <button
        type="button"
        aria-label={t("actions.delete")}
        title={t("actions.delete")}
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
