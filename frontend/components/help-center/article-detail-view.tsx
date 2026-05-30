"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type ArticleInput,
  useArticle,
  useCategories,
  useUpdateArticle,
} from "@/lib/api/portals";

import { ArticleForm } from "./article-form";

export function ArticleDetailView({
  accountId,
  slug,
  articleId,
}: {
  accountId: string;
  slug: string;
  articleId: number;
}) {
  const router = useRouter();
  const { data: article, isLoading, isError } = useArticle(
    accountId,
    slug,
    articleId,
  );
  const categories = useCategories(accountId, slug);
  const update = useUpdateArticle(accountId, slug);

  async function handleUpdate(input: ArticleInput) {
    await update.mutateAsync({ id: articleId, patch: input });
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 md:p-6">
      <Link
        href={`/accounts/${accountId}/help-center/${slug}`}
        className="inline-flex items-center gap-1 text-sm text-fg-muted hover:text-fg"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden />
        Volver al portal
      </Link>
      {isLoading ? (
        <p className="p-8 text-center text-sm text-fg-muted">Cargando…</p>
      ) : isError || !article ? (
        <p role="alert" className="p-8 text-center text-sm text-danger">
          No se pudo cargar el artículo.
        </p>
      ) : (
        <Card>
          <CardHeader>
            <CardTitle>{article.title}</CardTitle>
          </CardHeader>
          <CardContent>
            <ArticleForm
              categories={categories.data ?? []}
              initial={article}
              submitting={update.isPending}
              onSubmit={handleUpdate}
              onCancel={() =>
                router.push(`/accounts/${accountId}/help-center/${slug}`)
              }
            />
          </CardContent>
        </Card>
      )}
    </div>
  );
}
