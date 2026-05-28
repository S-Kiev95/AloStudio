import { FileText } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import type { Article, Category } from "@/lib/api/portals";
import { fetchArticles, fetchCategories, fetchPortal } from "@/lib/hc/fetch";

export const revalidate = 300;

export default async function PortalLandingPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  // Layout already 404s, but ensure the SSR data is here too.
  const portal = await fetchPortal(slug);
  if (!portal) notFound();

  const [categories, articles] = await Promise.all([
    fetchCategories(slug),
    fetchArticles(slug),
  ]);

  return (
    <div className="space-y-8">
      {portal.header_text ? (
        <p className="text-base leading-relaxed text-fg-muted">
          {portal.header_text}
        </p>
      ) : null}

      {categories.length > 0 ? (
        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-fg-muted">
            Categorías
          </h2>
          <ul className="grid gap-3 sm:grid-cols-2">
            {categories.map((c) => (
              <CategoryCard key={c.id} category={c} portalSlug={slug} />
            ))}
          </ul>
        </section>
      ) : null}

      <section>
        <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-fg-muted">
          Artículos recientes
        </h2>
        {articles.length === 0 ? (
          <p className="text-sm text-fg-muted">
            Todavía no hay artículos publicados.
          </p>
        ) : (
          <ul className="divide-y divide-border rounded-lg border border-border bg-surface">
            {articles.slice(0, 20).map((a) => (
              <ArticleRow key={a.id} article={a} portalSlug={slug} />
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function CategoryCard({
  category,
  portalSlug,
}: {
  category: Category;
  portalSlug: string;
}) {
  return (
    <li>
      <Link
        href={`/hc/${portalSlug}/categories/${category.slug}`}
        className="flex h-full flex-col gap-1 rounded-lg border border-border bg-surface p-4 transition-colors hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <span className="flex items-center gap-2 font-medium text-fg">
          <span className="text-xl">{category.icon ?? "📁"}</span>
          {category.name}
        </span>
        {category.description ? (
          <span className="line-clamp-2 text-xs text-fg-muted">
            {category.description}
          </span>
        ) : null}
      </Link>
    </li>
  );
}

function ArticleRow({
  article,
  portalSlug,
}: {
  article: Article;
  portalSlug: string;
}) {
  return (
    <li>
      <Link
        href={`/hc/${portalSlug}/articles/${article.slug}`}
        className="flex items-center gap-3 px-4 py-3 hover:bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
      >
        <FileText className="h-4 w-4 shrink-0 text-fg-muted" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-fg">{article.title}</p>
          {article.description ? (
            <p className="line-clamp-1 text-xs text-fg-muted">
              {article.description}
            </p>
          ) : null}
        </div>
      </Link>
    </li>
  );
}

