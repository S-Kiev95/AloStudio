"use client";

import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  type PortalInput,
  usePortal,
  useUpdatePortal,
} from "@/lib/api/portals";
import { cn } from "@/lib/utils";

import { ArticlesPanel } from "./articles-panel";
import { CategoriesPanel } from "./categories-panel";
import { PortalForm } from "./portal-form";

type Tab = "articles" | "categories" | "settings";

const TABS: { value: Tab; label: string }[] = [
  { value: "articles", label: "Artículos" },
  { value: "categories", label: "Categorías" },
  { value: "settings", label: "Ajustes" },
];

export function PortalDetailView({
  accountId,
  slug,
}: {
  accountId: string;
  slug: string;
}) {
  const { data: portal, isLoading, isError } = usePortal(accountId, slug);
  const update = useUpdatePortal(accountId);
  const [tab, setTab] = useState<Tab>("articles");

  async function handleUpdate(input: PortalInput) {
    await update.mutateAsync({ slug, patch: input });
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4 p-4 md:p-6">
      <Link
        href={`/accounts/${accountId}/help-center`}
        className="inline-flex items-center gap-1 text-sm text-fg-muted hover:text-fg"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden />
        Volver a portales
      </Link>

      {isLoading ? (
        <p className="p-8 text-center text-sm text-fg-muted">Cargando…</p>
      ) : isError || !portal ? (
        <p role="alert" className="p-8 text-center text-sm text-danger">
          No se pudo cargar el portal.
        </p>
      ) : (
        <>
          <div className="flex items-center gap-3">
            <span
              className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-white"
              style={{ backgroundColor: portal.color ?? "#1f93ff" }}
            >
              <span className="text-lg font-semibold">
                {portal.name.slice(0, 1).toUpperCase()}
              </span>
            </span>
            <div className="min-w-0 flex-1">
              <h2 className="truncate text-xl font-semibold text-fg">
                {portal.name}
              </h2>
              <p className="truncate text-xs text-fg-muted">/{portal.slug}</p>
            </div>
          </div>

          <div className="flex gap-1 border-b border-border">
            {TABS.map((t) => (
              <button
                key={t.value}
                type="button"
                onClick={() => setTab(t.value)}
                aria-pressed={tab === t.value}
                className={cn(
                  "-mb-px border-b-2 px-3 py-2 text-sm font-medium",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  tab === t.value
                    ? "border-primary text-fg"
                    : "border-transparent text-fg-muted hover:text-fg",
                )}
              >
                {t.label}
              </button>
            ))}
          </div>

          {tab === "articles" ? (
            <ArticlesPanel accountId={accountId} slug={slug} />
          ) : tab === "categories" ? (
            <CategoriesPanel accountId={accountId} slug={slug} />
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>Ajustes del portal</CardTitle>
              </CardHeader>
              <CardContent>
                <PortalForm
                  initial={portal}
                  submitting={update.isPending}
                  onSubmit={handleUpdate}
                  onCancel={() => setTab("articles")}
                />
              </CardContent>
            </Card>
          )}
        </>
      )}
    </div>
  );
}
