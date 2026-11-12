"use client";

import { Package, Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";

import { PageHeader } from "@/components/shell/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { SegmentedControl } from "@/components/ui/segmented-control";
import {
  type Product,
  type ProductInput,
  useCreateProduct,
  useDeleteProduct,
  useProducts,
  useUpdateProduct,
} from "@/lib/api/products";
import { cn } from "@/lib/utils";

import { ProductForm } from "./product-form";
import { useT } from "@/lib/i18n/provider";
import type { MessageKey } from "@/lib/i18n/translate";

const FILTERS: { value: "all" | "active" | "inactive"; label: MessageKey }[] = [
  { value: "all", label: "products.filters.all" },
  { value: "active", label: "products.filters.active" },
  { value: "inactive", label: "products.filters.inactive" },
];

export function ProductsView({ accountId }: { accountId: string }) {
  const t = useT();
  const [filter, setFilter] = useState<"all" | "active" | "inactive">("all");
  const [editing, setEditing] = useState<Product | null>(null);
  const [creating, setCreating] = useState(false);

  const enabled =
    filter === "all" ? undefined : filter === "active" ? true : false;
  const { data, isLoading, isError } = useProducts(accountId, { enabled });
  const create = useCreateProduct(accountId);
  const update = useUpdateProduct(accountId);

  async function handleCreate(input: ProductInput) {
    await create.mutateAsync(input);
    setCreating(false);
  }

  async function handleUpdate(input: ProductInput) {
    if (!editing) return;
    await update.mutateAsync({ id: editing.id, patch: input });
    setEditing(null);
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title={t("products.title")}
        actions={
          !creating && !editing ? (
            <Button size="sm" onClick={() => setCreating(true)}>
              <Plus className="h-4 w-4" aria-hidden />
              {t("products.new")}
            </Button>
          ) : undefined
        }
      />

      {creating ? (
        <Card>
          <CardHeader>
            <CardTitle>{t("products.new")}</CardTitle>
          </CardHeader>
          <CardContent>
            <ProductForm
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
            <CardTitle>{t("products.edit")}</CardTitle>
          </CardHeader>
          <CardContent>
            <ProductForm
              initial={editing}
              submitting={update.isPending}
              onSubmit={handleUpdate}
              onCancel={() => setEditing(null)}
            />
          </CardContent>
        </Card>
      ) : null}

      <SegmentedControl
        ariaLabel={t("products.filterLabel")}
        size="sm"
        value={filter}
        onValueChange={setFilter}
        options={FILTERS.map((o) => ({ ...o, label: t(o.label) }))}
      />

      <div className="overflow-hidden rounded-md border border-glass bg-surface">
        {isLoading ? (
          <p className="p-8 text-center text-sm text-fg-muted">{t("common.loading")}</p>
        ) : isError ? (
          <p role="alert" className="p-8 text-center text-sm text-danger">
            {t("products.loadFailed")}
          </p>
        ) : (data?.length ?? 0) === 0 ? (
          <p className="p-8 text-center text-sm text-fg-muted">
            {t("products.empty")}
          </p>
        ) : (
          <ul className="divide-y divide-glass">
            {data?.map((p) => (
              <ProductRow
                key={p.id}
                accountId={accountId}
                product={p}
                onEdit={() => {
                  setCreating(false);
                  setEditing(p);
                }}
              />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function ProductRow({
  accountId,
  product,
  onEdit,
}: {
  accountId: string;
  product: Product;
  onEdit: () => void;
}) {
  const t = useT();
  const del = useDeleteProduct(accountId);
  const [error, setError] = useState<string | null>(null);

  async function onDelete() {
    if (!window.confirm(t("products.deleteConfirm", { name: product.name }))) return;
    setError(null);
    try {
      await del.mutateAsync(product.id);
    } catch (e) {
      setError((e as { message?: string })?.message ?? t("actions.deleteFailed"));
    }
  }

  const priceLabel =
    product.price != null
      ? `${product.price}${product.currency ? ` ${product.currency}` : ""}`
      : "—";

  return (
    <li className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-hover-glass">
      <div className="grid h-12 w-12 shrink-0 place-items-center overflow-hidden rounded-md border border-glass bg-surface-2 text-fg-muted">
        {product.image_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={product.image_url}
            alt=""
            loading="lazy"
            className="h-full w-full object-cover"
          />
        ) : (
          <Package className="h-5 w-5" aria-hidden />
        )}
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-fg">{product.name}</p>
        <p className="font-numeric text-xs tabular-nums text-fg-muted">
          {priceLabel}
          {product.sku ? ` · SKU ${product.sku}` : ""}
        </p>
        {error ? (
          <p role="alert" className="text-xs text-danger">
            {error}
          </p>
        ) : null}
      </div>
      <span
        className={cn(
          "rounded-pill px-2 py-0.5 text-xs font-medium",
          product.enabled
            ? "bg-success/10 text-success"
            : "bg-surface-2 text-fg-muted",
        )}
      >
        {product.enabled ? t("products.active") : t("products.inactive")}
      </span>
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
