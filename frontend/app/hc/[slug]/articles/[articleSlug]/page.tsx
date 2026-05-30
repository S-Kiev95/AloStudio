import { ChevronRight } from "lucide-react";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Markdown } from "@/components/help-center-public/markdown";
import { fetchArticle, fetchCategories, fetchPortal } from "@/lib/hc/fetch";

export const revalidate = 300;

export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string; articleSlug: string }>;
}) {
  const { slug, articleSlug } = await params;
  const [portal, article] = await Promise.all([
    fetchPortal(slug),
    fetchArticle(slug, articleSlug),
  ]);
  if (!portal || !article) return { title: "Not found" };
  return {
    title: `${article.title} · ${portal.name}`,
    description: article.description || undefined,
    openGraph: {
      title: article.title,
      description: article.description || undefined,
      type: "article",
    },
  };
}

export default async function ArticlePage({
  params,
}: {
  params: Promise<{ slug: string; articleSlug: string }>;
}) {
  const { slug, articleSlug } = await params;
  const portal = await fetchPortal(slug);
  if (!portal) notFound();

  const article = await fetchArticle(slug, articleSlug);
  if (!article) notFound();

  // Resolve the category for the breadcrumb (best-effort, doesn't 404 if missing).
  const categories = await fetchCategories(slug);
  const category = article.category_id
    ? categories.find((c) => c.id === article.category_id)
    : null;

  return (
    <article className="space-y-6">
      <nav className="flex flex-wrap items-center gap-1 text-sm text-fg-muted">
        <Link
          href={`/hc/${slug}`}
          className="hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {portal.name}
        </Link>
        {category ? (
          <>
            <ChevronRight className="h-3.5 w-3.5" aria-hidden />
            <Link
              href={`/hc/${slug}/categories/${category.slug}`}
              className="hover:text-fg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {category.name}
            </Link>
          </>
        ) : null}
        <ChevronRight className="h-3.5 w-3.5" aria-hidden />
        <span className="truncate text-fg">{article.title}</span>
      </nav>

      <header className="space-y-2">
        <h1 className="text-3xl font-semibold tracking-tight text-fg">
          {article.title}
        </h1>
        {article.description ? (
          <p className="text-lg text-fg-muted">{article.description}</p>
        ) : null}
      </header>

      {article.content ? (
        <Markdown source={article.content} />
      ) : (
        <p className="text-sm text-fg-muted">
          Este artículo todavía no tiene contenido.
        </p>
      )}
    </article>
  );
}
