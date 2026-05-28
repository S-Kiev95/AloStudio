import "server-only";

import { cache } from "react";

import type { Article, Category, Portal } from "@/lib/api/portals";

const BACKEND = process.env.BACKEND_INTERNAL_URL ?? "http://localhost:8000";

/** ISR revalidation window — 5 minutes. Keeps the SEO surface fresh
 * without hammering the backend. */
const REVALIDATE_SECONDS = 300;

async function fetchJson<T>(path: string): Promise<T | null> {
  try {
    const res = await fetch(`${BACKEND}${path}`, {
      next: { revalidate: REVALIDATE_SECONDS, tags: ["hc"] },
    });
    if (!res.ok) return null;
    return (await res.json()) as T;
  } catch {
    return null;
  }
}

/**
 * React ``cache()`` deduplicates a fetch within one server request — the
 * portal layout + the child page can both call ``fetchPortal(slug)`` and
 * share the result.
 */
export const fetchPortal = cache(async (slug: string): Promise<Portal | null> => {
  return fetchJson<Portal>(`/hc/${encodeURIComponent(slug)}`);
});

export const fetchCategories = cache(
  async (slug: string, locale?: string): Promise<Category[]> => {
    const qs = locale ? `?locale=${encodeURIComponent(locale)}` : "";
    return (
      (await fetchJson<Category[]>(
        `/hc/${encodeURIComponent(slug)}/categories${qs}`,
      )) ?? []
    );
  },
);

export type FetchArticlesOpts = {
  locale?: string;
  category_slug?: string;
};

export const fetchArticles = cache(
  async (slug: string, opts: FetchArticlesOpts = {}): Promise<Article[]> => {
    const sp = new URLSearchParams();
    if (opts.locale) sp.set("locale", opts.locale);
    if (opts.category_slug) sp.set("category_slug", opts.category_slug);
    const qs = sp.toString();
    return (
      (await fetchJson<Article[]>(
        `/hc/${encodeURIComponent(slug)}/articles${qs ? `?${qs}` : ""}`,
      )) ?? []
    );
  },
);

export const fetchArticle = cache(
  async (
    slug: string,
    articleSlug: string,
    locale?: string,
  ): Promise<Article | null> => {
    const qs = locale ? `?locale=${encodeURIComponent(locale)}` : "";
    return fetchJson<Article>(
      `/hc/${encodeURIComponent(slug)}/articles/${encodeURIComponent(
        articleSlug,
      )}${qs}`,
    );
  },
);
