import { ChevronRight, FileText } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { fetchArticles, fetchCategories, fetchPortal } from "@/lib/hc/fetch";

export const revalidate = 300;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string; categorySlug: string }>;
}) {
  const { slug, categorySlug } = await params;
  const portal = await fetchPortal(slug);
  const categories = portal ? await fetchCategories(slug) : [];
  const category = categories.find((c) => c.slug === categorySlug);
  if (!portal || !category) return { title: "Not found" };
  return {
    title: `${category.name} · ${portal.name}`,
    description: category.description || undefined,
  };
}

export default async function CategoryPage({
  params,
}: {
  params: Promise<{ slug: string; categorySlug: string }>;
}) {
  const { slug, categorySlug } = await params;
  const portal = await fetchPortal(slug);
  if (!portal) notFound();

  const categories = await fetchCategories(slug);
  const category = categories.find((c) => c.slug === categorySlug);
  if (!category) notFound();

  const articles = await fetchArticles(slug, { category_slug: categorySlug });

  return (
    <div className="space-y-6">
      <nav className="flex items-center gap-1 text-sm text-fg-muted">
        <Link
          href={`/hc/${slug}`}
          className="hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {portal.name}
        </Link>
        <ChevronRight className="h-3.5 w-3.5" aria-hidden />
        <span className="text-fg">{category.name}</span>
      </nav>

      <div className="flex items-start gap-3">
        <span className="text-3xl" aria-hidden>
          {category.icon ?? "📁"}
        </span>
        <div>
          <h1 className="text-2xl font-semibold text-fg">{category.name}</h1>
          {category.description ? (
            <p className="mt-1 text-fg-muted">{category.description}</p>
          ) : null}
        </div>
      </div>

      {articles.length === 0 ? (
        <p className="text-sm text-fg-muted">
          No hay artículos publicados en esta categoría todavía.
        </p>
      ) : (
        <ul className="divide-y divide-border rounded-lg border border-border bg-surface">
          {articles.map((a) => (
            <li key={a.id}>
              <Link
                href={`/hc/${slug}/articles/${a.slug}`}
                className="flex items-center gap-3 px-4 py-3 hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
              >
                <FileText
                  className="h-4 w-4 shrink-0 text-fg-muted"
                  aria-hidden
                />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-fg">
                    {a.title}
                  </p>
                  {a.description ? (
                    <p className="line-clamp-1 text-xs text-fg-muted">
                      {a.description}
                    </p>
                  ) : null}
                </div>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
