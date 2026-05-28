"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type ArticleInput,
  useCategories,
  useCreateArticle,
} from "@/lib/api/portals";

import { ArticleForm } from "./article-form";

export function ArticleNewView({
  accountId,
  slug,
}: {
  accountId: string;
  slug: string;
}) {
  const router = useRouter();
  const categories = useCategories(accountId, slug);
  const create = useCreateArticle(accountId, slug);

  async function handleCreate(input: ArticleInput) {
    const art = await create.mutateAsync(input);
    router.push(
      `/accounts/${accountId}/help-center/${slug}/articles/${art.id}`,
    );
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
      <Card>
        <CardHeader>
          <CardTitle>Nuevo artículo</CardTitle>
        </CardHeader>
        <CardContent>
          <ArticleForm
            categories={categories.data ?? []}
            submitting={create.isPending}
            onSubmit={handleCreate}
            onCancel={() =>
              router.push(`/accounts/${accountId}/help-center/${slug}`)
            }
          />
        </CardContent>
      </Card>
    </div>
  );
}
