"use client";

import { ChevronRight, Plus, Trash2, Zap } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { buttonVariants } from "@/components/ui/button";
import {
  type Macro,
  useDeleteMacro,
  useMacros,
} from "@/lib/api/macros";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n/provider";

export function MacrosView({ accountId }: { accountId: string }) {
  const t = useT();
  const { data, isLoading, isError } = useMacros(accountId);

  return (
    <div className="max-w-3xl space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-medium text-fg">{t("settings.items.macros")}</h2>
        <Link
          href={`/accounts/${accountId}/settings/macros/new`}
          className={buttonVariants({ size: "sm" })}
        >
          <Plus className="h-4 w-4" aria-hidden />
          {t("settingsMacros.new")}
        </Link>
      </div>

      <div className="overflow-hidden rounded-md border border-glass bg-surface">
        {isLoading ? (
          <p className="p-8 text-center text-sm text-fg-muted">{t("common.loading")}</p>
        ) : isError ? (
          <p role="alert" className="p-8 text-center text-sm text-danger">
            {t("settingsMacros.listLoadFailed")}
          </p>
        ) : (data?.length ?? 0) === 0 ? (
          <p className="p-8 text-center text-sm text-fg-muted">
            {t("settingsMacros.empty")}
          </p>
        ) : (
          <ul className="divide-y divide-glass">
            {data?.map((m) => (
              <MacroRow key={m.id} accountId={accountId} macro={m} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function MacroRow({ accountId, macro }: { accountId: string; macro: Macro }) {
  const t = useT();
  const del = useDeleteMacro(accountId);
  const [error, setError] = useState<string | null>(null);

  async function onDelete(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    if (!window.confirm(t("settingsMacros.deleteConfirm", { name: macro.name }))) return;
    setError(null);
    try {
      await del.mutateAsync(macro.id);
    } catch (err) {
      setError((err as { message?: string })?.message ?? t("actions.deleteFailed"));
    }
  }

  return (
    <li className="flex items-center gap-1 pr-2 transition-colors hover:bg-hover-glass">
      <Link
        href={`/accounts/${accountId}/settings/macros/${macro.id}`}
        className="flex min-w-0 flex-1 items-center gap-3 px-4 py-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
      >
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-focused text-lit">
          <Zap className="h-4 w-4" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-fg">{macro.name}</p>
          <p className="text-xs text-fg-muted">
            {t(
              macro.actions.length === 1
                ? "settingsMacros.actionsOne"
                : "settingsMacros.actionsMany",
              { count: macro.actions.length },
            )}
            {macro.created_by
              ? ` · ${t("settingsMacros.by", { name: macro.created_by.name })}`
              : ""}
          </p>
          {error ? (
            <p role="alert" className="text-xs text-danger">
              {error}
            </p>
          ) : null}
        </div>
        <span
          className={cn(
            "rounded-sm px-2 py-0.5 text-xs font-medium",
            macro.visibility === "global"
              ? "bg-focused text-lit"
              : "bg-surface-2 text-fg-muted",
          )}
        >
          {macro.visibility === "global" ? t("settingsMacros.global") : t("settingsMacros.personal")}
        </span>
      </Link>
      <button
        type="button"
        aria-label={t("actions.delete")}
        title={t("actions.delete")}
        onClick={onDelete}
        disabled={del.isPending}
        className="rounded-md p-1.5 text-fg-muted hover:bg-surface-2 hover:text-danger disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Trash2 className="h-4 w-4" aria-hidden />
      </button>
      <ChevronRight className="h-4 w-4 shrink-0 text-fg-muted" aria-hidden />
    </li>
  );
}
