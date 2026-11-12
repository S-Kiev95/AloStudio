"use client";

import { Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type Category,
  type CategoryInput,
  useCategories,
  useCreateCategory,
  useDeleteCategory,
  useUpdateCategory,
} from "@/lib/api/portals";

import { CategoryForm } from "./category-form";
import { useT } from "@/lib/i18n/provider";

export function CategoriesPanel({
  accountId,
  slug,
  locale,
}: {
  accountId: string;
  slug: string;
  locale?: string;
}) {
  const t = useT();
  const { data, isLoading, isError } = useCategories(accountId, slug, locale);
  const create = useCreateCategory(accountId, slug);
  const update = useUpdateCategory(accountId, slug);

  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Category | null>(null);

  async function handleCreate(input: CategoryInput) {
    await create.mutateAsync(input);
    setCreating(false);
  }

  async function handleUpdate(input: CategoryInput) {
    if (!editing) return;
    await update.mutateAsync({ id: editing.id, patch: input });
    setEditing(null);
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-fg">{t("hc.categories")}</h3>
        {!creating && !editing ? (
          <Button size="sm" variant="ghost" onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" aria-hidden />
            {t("helpCenter.newCategory")}
          </Button>
        ) : null}
      </div>

      {creating ? (
        <Card>
          <CardHeader>
            <CardTitle>{t("helpCenter.newCategory")}</CardTitle>
          </CardHeader>
          <CardContent>
            <CategoryForm
              submitting={create.isPending}
              onSubmit={handleCreate}
              onCancel={() => setCreating(false)}
            />
          </CardContent>
        </Card>
      ) : null}

      {editing ? (
        <Card>
          <CardHeader>
            <CardTitle>{t("helpCenter.editCategory")}</CardTitle>
          </CardHeader>
          <CardContent>
            <CategoryForm
              initial={editing}
              submitting={update.isPending}
              onSubmit={handleUpdate}
              onCancel={() => setEditing(null)}
            />
          </CardContent>
        </Card>
      ) : null}

      <div className="overflow-hidden rounded-md border border-glass bg-surface">
        {isLoading ? (
          <p className="p-6 text-center text-sm text-fg-muted">{t("common.loading")}</p>
        ) : isError ? (
          <p role="alert" className="p-6 text-center text-sm text-danger">
            {t("helpCenter.categoriesLoadFailed")}
          </p>
        ) : (data?.length ?? 0) === 0 ? (
          <p className="p-6 text-center text-sm text-fg-muted">
            {t("helpCenter.noCategories")}
          </p>
        ) : (
          <ul className="divide-y divide-glass">
            {data?.map((c) => (
              <CategoryRow
                key={c.id}
                accountId={accountId}
                slug={slug}
                category={c}
                onEdit={() => {
                  setCreating(false);
                  setEditing(c);
                }}
              />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function CategoryRow({
  accountId,
  slug,
  category,
  onEdit,
}: {
  accountId: string;
  slug: string;
  category: Category;
  onEdit: () => void;
}) {
  const t = useT();
  const del = useDeleteCategory(accountId, slug);
  const [error, setError] = useState<string | null>(null);

  async function onDelete() {
    if (!window.confirm(t("helpCenter.deleteCategoryConfirm", { name: category.name }))) return;
    setError(null);
    try {
      await del.mutateAsync(category.id);
    } catch (e) {
      setError((e as { message?: string })?.message ?? t("actions.deleteFailed"));
    }
  }

  return (
    <li className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-hover-glass">
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-sm bg-surface-2 text-sm">
        {category.icon ?? "📁"}
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-fg">{category.name}</p>
        <p className="truncate text-xs text-fg-muted">
          /{category.slug}
          {category.locale ? ` · ${category.locale}` : ""}
        </p>
        {error ? (
          <p role="alert" className="text-xs text-danger">
            {error}
          </p>
        ) : null}
      </div>
      <button
        type="button"
        aria-label={t("actions.edit")}
        title={t("actions.edit")}
        onClick={onEdit}
        className="rounded-md p-1.5 text-fg-muted hover:bg-hover-glass hover:text-fg focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon"
      >
        <Pencil className="h-4 w-4" aria-hidden />
      </button>
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
    </li>
  );
}
