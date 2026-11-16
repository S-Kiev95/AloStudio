"use client";

import { ArrowLeft, RefreshCw } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { selectClassName } from "@/components/ui/select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  type PortalInput,
  usePortal,
  useReindexPortal,
  useUpdatePortal,
} from "@/lib/api/portals";
import { cn } from "@/lib/utils";

import { ArticlesPanel } from "./articles-panel";
import { CategoriesPanel } from "./categories-panel";
import { PortalForm } from "./portal-form";
import { useT } from "@/lib/i18n/provider";
import type { MessageKey } from "@/lib/i18n/translate";

type Tab = "articles" | "categories" | "settings";

const TABS: { value: Tab; label: MessageKey }[] = [
  { value: "articles", label: "helpCenter.articles" },
  { value: "categories", label: "hc.categories" },
  { value: "settings", label: "nav.settings" },
];

export function PortalDetailView({
  accountId,
  slug,
}: {
  accountId: string;
  slug: string;
}) {
  const t = useT();
  const { data: portal, isLoading, isError } = usePortal(accountId, slug);
  const update = useUpdatePortal(accountId);
  const [tab, setTab] = useState<Tab>("articles");
  const [locale, setLocale] = useState("");

  const rawLocales = (
    portal?.config as { allowed_locales?: unknown } | undefined
  )?.allowed_locales;
  const allowedLocales = Array.isArray(rawLocales)
    ? rawLocales.filter((x): x is string => typeof x === "string")
    : [];

  async function handleUpdate(input: PortalInput) {
    await update.mutateAsync({ slug, patch: input });
  }

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <Link
        href={`/accounts/${accountId}/help-center`}
        className="inline-flex items-center gap-1 text-sm text-fg-muted hover:text-fg"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden />
        {t("helpCenter.backToPortals")}
      </Link>

      {isLoading ? (
        <p className="p-8 text-center text-sm text-fg-muted">{t("common.loading")}</p>
      ) : isError || !portal ? (
        <p role="alert" className="p-8 text-center text-sm text-danger">
          {t("helpCenter.portalLoadFailed")}
        </p>
      ) : (
        <>
          <div className="flex items-center gap-3">
            {portal.logo ? (
              <span className="flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-full">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={portal.logo}
                  alt={portal.name}
                  className="h-full w-full object-cover"
                />
              </span>
            ) : (
              <span
                className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-white"
                style={{ backgroundColor: portal.color ?? "#1f93ff" }}
              >
                <span className="text-lg font-semibold">
                  {portal.name.slice(0, 1).toUpperCase()}
                </span>
              </span>
            )}
            <div className="min-w-0 flex-1">
              <h2 className="truncate text-xl font-medium text-fg">
                {portal.name}
              </h2>
              <p className="truncate text-xs text-fg-muted">/{portal.slug}</p>
            </div>
            {tab === "articles" ? (
              <ReindexButton accountId={accountId} slug={slug} />
            ) : null}
            {tab !== "settings" && allowedLocales.length > 1 ? (
              <select
                value={locale}
                onChange={(e) => setLocale(e.target.value)}
                aria-label={t("auth.language")}
                className={cn(selectClassName("sm"), "shrink-0")}
              >
                <option value="">{t("helpCenter.allLanguages")}</option>
                {allowedLocales.map((l) => (
                  <option key={l} value={l}>
                    {l}
                  </option>
                ))}
              </select>
            ) : null}
          </div>

          <Tabs value={tab} onValueChange={(v) => setTab(v as Tab)}>
            <TabsList>
              {TABS.map((tab) => (
                <TabsTrigger key={tab.value} value={tab.value}>
                  {t(tab.label)}
                </TabsTrigger>
              ))}
            </TabsList>
          </Tabs>

          {tab === "articles" ? (
            <ArticlesPanel
              accountId={accountId}
              slug={slug}
              locale={locale || undefined}
            />
          ) : tab === "categories" ? (
            <CategoriesPanel
              accountId={accountId}
              slug={slug}
              locale={locale || undefined}
            />
          ) : (
            <Card>
              <CardHeader>
                <CardTitle>{t("helpCenter.portalSettings")}</CardTitle>
              </CardHeader>
              <CardContent>
                <PortalForm
                  accountId={accountId}
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

function ReindexButton({
  accountId,
  slug,
}: {
  accountId: string;
  slug: string;
}) {
  const t = useT();
  const reindex = useReindexPortal(accountId, slug);
  const [msg, setMsg] = useState<string | null>(null);

  async function run() {
    setMsg(null);
    try {
      const { enqueued } = await reindex.mutateAsync();
      setMsg(
        enqueued > 0
          ? t(
              enqueued === 1 ? "helpCenter.reindexingOne" : "helpCenter.reindexingMany",
              { count: enqueued },
            )
          : t("helpCenter.semanticOff"),
      );
    } catch {
      setMsg(t("helpCenter.reindexFailed"));
    }
  }

  return (
    <div className="flex shrink-0 flex-col items-end gap-0.5">
      <button
        type="button"
        onClick={run}
        disabled={reindex.isPending}
        title={t("helpCenter.reindexHint")}
        className="inline-flex items-center gap-1.5 rounded-control border border-glass bg-field px-2.5 py-1.5 text-xs font-medium text-fg hover:bg-hover-glass disabled:opacity-50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon"
      >
        <RefreshCw
          className={cn("h-3.5 w-3.5", reindex.isPending && "animate-spin")}
          aria-hidden
        />
        {t("helpCenter.reindex")}
      </button>
      {msg ? (
        <span className="text-[10px] text-fg-muted" role="status">
          {msg}
        </span>
      ) : null}
    </div>
  );
}
