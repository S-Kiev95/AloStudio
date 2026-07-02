import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "./fetcher";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------
export type ArticleStatus = "draft" | "published" | "archived";

export const ARTICLE_STATUSES: { value: ArticleStatus; label: string }[] = [
  { value: "draft", label: "Borrador" },
  { value: "published", label: "Publicado" },
  { value: "archived", label: "Archivado" },
];

export type Portal = {
  id: number;
  account_id: number;
  name: string;
  slug: string;
  custom_domain: string | null;
  color: string | null;
  homepage_link: string | null;
  page_title: string | null;
  header_text: string | null;
  config: Record<string, unknown>;
  archived: boolean;
};

export type Category = {
  id: number;
  account_id: number;
  portal_id: number;
  name: string;
  description: string | null;
  position: number | null;
  locale: string | null;
  slug: string;
  icon: string | null;
  parent_category_id: number | null;
  associated_category_id: number | null;
};

export type Article = {
  id: number;
  account_id: number;
  portal_id: number;
  category_id: number | null;
  title: string;
  description: string | null;
  content: string | null;
  status: ArticleStatus;
  views: number;
  author_id: number | null;
  slug: string;
  locale: string | null;
  position: number | null;
  meta: Record<string, unknown>;
};

export type PortalInput = {
  name: string;
  slug?: string;
  custom_domain?: string | null;
  color?: string | null;
  homepage_link?: string | null;
  page_title?: string | null;
  header_text?: string | null;
  archived?: boolean;
};

export type CategoryInput = {
  name: string;
  slug?: string;
  description?: string | null;
  position?: number | null;
  locale?: string | null;
  icon?: string | null;
};

export type ArticleInput = {
  title: string;
  slug?: string;
  description?: string | null;
  content?: string | null;
  category_id?: number | null;
  locale?: string | null;
  position?: number | null;
  status?: ArticleStatus;
};

// ---------------------------------------------------------------------------
// URL helpers
// ---------------------------------------------------------------------------
function portalsBase(accountId: string): string {
  return `/api/v1/accounts/${accountId}/portals`;
}
function categoriesBase(accountId: string, slug: string): string {
  return `${portalsBase(accountId)}/${slug}/categories`;
}
function articlesBase(accountId: string, slug: string): string {
  return `${portalsBase(accountId)}/${slug}/articles`;
}

// ---------------------------------------------------------------------------
// Portals
// ---------------------------------------------------------------------------
export function usePortals(accountId: string) {
  return useQuery({
    queryKey: ["portals", accountId],
    queryFn: () => apiFetch<Portal[]>(portalsBase(accountId)),
  });
}

export function usePortal(accountId: string, slug: string) {
  return useQuery({
    queryKey: ["portal", accountId, slug],
    queryFn: () => apiFetch<Portal>(`${portalsBase(accountId)}/${slug}`),
    enabled: Boolean(slug),
  });
}

function invalidatePortals(
  qc: ReturnType<typeof useQueryClient>,
  accountId: string,
) {
  qc.invalidateQueries({ queryKey: ["portals", accountId] });
  qc.invalidateQueries({ queryKey: ["portal", accountId] });
}

export function useCreatePortal(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: PortalInput) =>
      apiFetch<Portal>(portalsBase(accountId), {
        method: "POST",
        body: JSON.stringify({ portal: input }),
      }),
    onSuccess: () => invalidatePortals(qc, accountId),
  });
}

export function useUpdatePortal(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { slug: string; patch: PortalInput }) =>
      apiFetch<Portal>(`${portalsBase(accountId)}/${input.slug}`, {
        method: "PATCH",
        body: JSON.stringify({ portal: input.patch }),
      }),
    onSuccess: () => invalidatePortals(qc, accountId),
  });
}

export function useDeletePortal(accountId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (slug: string) =>
      apiFetch<Record<string, never>>(`${portalsBase(accountId)}/${slug}`, {
        method: "DELETE",
      }),
    onSuccess: () => invalidatePortals(qc, accountId),
  });
}

// ---------------------------------------------------------------------------
// Categories
// ---------------------------------------------------------------------------
export function useCategories(
  accountId: string,
  slug: string,
  locale?: string,
) {
  return useQuery({
    queryKey: ["portal-categories", accountId, slug, locale ?? null],
    queryFn: () => {
      const qs = locale ? `?locale=${encodeURIComponent(locale)}` : "";
      return apiFetch<Category[]>(`${categoriesBase(accountId, slug)}${qs}`);
    },
    enabled: Boolean(slug),
  });
}

function invalidateCategories(
  qc: ReturnType<typeof useQueryClient>,
  accountId: string,
  slug: string,
) {
  qc.invalidateQueries({ queryKey: ["portal-categories", accountId, slug] });
}

export function useCreateCategory(accountId: string, slug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: CategoryInput) =>
      apiFetch<Category>(categoriesBase(accountId, slug), {
        method: "POST",
        body: JSON.stringify({ category: input }),
      }),
    onSuccess: () => invalidateCategories(qc, accountId, slug),
  });
}

export function useUpdateCategory(accountId: string, slug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { id: number; patch: CategoryInput }) =>
      apiFetch<Category>(`${categoriesBase(accountId, slug)}/${input.id}`, {
        method: "PATCH",
        body: JSON.stringify({ category: input.patch }),
      }),
    onSuccess: () => invalidateCategories(qc, accountId, slug),
  });
}

export function useDeleteCategory(accountId: string, slug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<Record<string, never>>(
        `${categoriesBase(accountId, slug)}/${id}`,
        { method: "DELETE" },
      ),
    onSuccess: () => invalidateCategories(qc, accountId, slug),
  });
}

// ---------------------------------------------------------------------------
// Articles
// ---------------------------------------------------------------------------
export type ArticleFilters = {
  locale?: string;
  status?: ArticleStatus;
  category_id?: number;
  query?: string;
};

export function useArticles(
  accountId: string,
  slug: string,
  filters: ArticleFilters = {},
) {
  return useQuery({
    queryKey: [
      "portal-articles",
      accountId,
      slug,
      filters.locale ?? null,
      filters.status ?? null,
      filters.category_id ?? null,
      filters.query ?? null,
    ],
    queryFn: () => {
      const sp = new URLSearchParams();
      if (filters.locale) sp.set("locale", filters.locale);
      if (filters.status) sp.set("status", filters.status);
      if (filters.category_id !== undefined)
        sp.set("category_id", String(filters.category_id));
      if (filters.query) sp.set("query", filters.query);
      const qs = sp.toString();
      return apiFetch<Article[]>(
        `${articlesBase(accountId, slug)}${qs ? `?${qs}` : ""}`,
      );
    },
    enabled: Boolean(slug),
  });
}

export function useArticle(accountId: string, slug: string, articleId: number) {
  return useQuery({
    queryKey: ["portal-article", accountId, slug, articleId],
    queryFn: () =>
      apiFetch<Article>(`${articlesBase(accountId, slug)}/${articleId}`),
    enabled: Boolean(slug) && Number.isFinite(articleId),
  });
}

function invalidateArticles(
  qc: ReturnType<typeof useQueryClient>,
  accountId: string,
  slug: string,
) {
  qc.invalidateQueries({ queryKey: ["portal-articles", accountId, slug] });
  qc.invalidateQueries({ queryKey: ["portal-article", accountId, slug] });
}

export function useCreateArticle(accountId: string, slug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: ArticleInput) =>
      apiFetch<Article>(articlesBase(accountId, slug), {
        method: "POST",
        body: JSON.stringify({ article: input }),
      }),
    onSuccess: () => invalidateArticles(qc, accountId, slug),
  });
}

export function useUpdateArticle(accountId: string, slug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { id: number; patch: ArticleInput }) =>
      apiFetch<Article>(`${articlesBase(accountId, slug)}/${input.id}`, {
        method: "PATCH",
        body: JSON.stringify({ article: input.patch }),
      }),
    onSuccess: () => invalidateArticles(qc, accountId, slug),
  });
}

export function useDeleteArticle(accountId: string, slug: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) =>
      apiFetch<Record<string, never>>(
        `${articlesBase(accountId, slug)}/${id}`,
        { method: "DELETE" },
      ),
    onSuccess: () => invalidateArticles(qc, accountId, slug),
  });
}
