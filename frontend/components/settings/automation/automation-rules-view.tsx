"use client";

import { ChevronRight, Copy, Plus, Trash2, Zap } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { buttonVariants } from "@/components/ui/button";
import {
  AUTOMATION_EVENT_LABELS,
  type AutomationRule,
  useAutomationRules,
  useCloneAutomationRule,
  useDeleteAutomationRule,
  useUpdateAutomationRule,
} from "@/lib/api/automation-rules";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n/provider";

export function AutomationRulesView({ accountId }: { accountId: string }) {
  const t = useT();
  const { data, isLoading, isError } = useAutomationRules(accountId);

  return (
    <div className="max-w-3xl space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-xl font-medium text-fg">{t("settings.items.automation")}</h2>
        <Link
          href={`/accounts/${accountId}/settings/automation/new`}
          className={buttonVariants({ size: "sm" })}
        >
          <Plus className="h-4 w-4" aria-hidden />
          {t("settingsAutomation.new")}
        </Link>
      </div>

      <div className="overflow-hidden rounded-md border border-glass bg-surface">
        {isLoading ? (
          <p className="p-8 text-center text-sm text-fg-muted">{t("common.loading")}</p>
        ) : isError ? (
          <p role="alert" className="p-8 text-center text-sm text-danger">
            {t("settingsAutomation.listLoadFailed")}
          </p>
        ) : (data?.length ?? 0) === 0 ? (
          <p className="p-8 text-center text-sm text-fg-muted">
            {t("settingsAutomation.empty")}
          </p>
        ) : (
          <ul className="divide-y divide-glass">
            {data?.map((r) => (
              <RuleRow key={r.id} accountId={accountId} rule={r} />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function RuleRow({
  accountId,
  rule,
}: {
  accountId: string;
  rule: AutomationRule;
}) {
  const t = useT();
  const update = useUpdateAutomationRule(accountId);
  const del = useDeleteAutomationRule(accountId);
  const clone = useCloneAutomationRule(accountId);
  const [error, setError] = useState<string | null>(null);

  async function run(
    fn: () => Promise<unknown>,
    fallback: string,
    stopEvent?: React.MouseEvent,
  ) {
    if (stopEvent) {
      stopEvent.preventDefault();
      stopEvent.stopPropagation();
    }
    setError(null);
    try {
      await fn();
    } catch (e) {
      setError((e as { message?: string })?.message ?? fallback);
    }
  }

  return (
    <li className="flex items-center gap-1 pr-2 transition-colors hover:bg-hover-glass">
      <Link
        href={`/accounts/${accountId}/settings/automation/${rule.id}`}
        className="flex min-w-0 flex-1 items-center gap-3 px-4 py-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring"
      >
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-focused text-lit">
          <Zap className="h-4 w-4" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-medium text-fg">{rule.name}</p>
          <p className="truncate text-xs text-fg-muted">
            {t(AUTOMATION_EVENT_LABELS[rule.event_name])} ·{" "}
            {t(
              rule.conditions.length === 1
                ? "settingsAutomation.conditionsOne"
                : "settingsAutomation.conditionsMany",
              { count: rule.conditions.length },
            )}{" "}
            ·{" "}
            {t(
              rule.actions.length === 1
                ? "settingsMacros.actionsOne"
                : "settingsMacros.actionsMany",
              { count: rule.actions.length },
            )}
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
            rule.active
              ? "bg-success/10 text-success"
              : "bg-surface-2 text-fg-muted",
          )}
        >
          {rule.active ? t("settingsAutomation.active") : t("campaigns.inactive")}
        </span>
      </Link>
      <button
        type="button"
        role="switch"
        aria-checked={rule.active}
        aria-label={rule.active ? t("settingsNotif.disable") : t("settingsNotif.enable")}
        title={rule.active ? t("settingsNotif.disable") : t("settingsNotif.enable")}
        onClick={(e) =>
          run(
            () =>
              update.mutateAsync({
                id: rule.id,
                patch: { active: !rule.active },
              }),
            t("settingsAutomation.toggleFailed"),
            e,
          )
        }
        disabled={update.isPending}
        className={cn(
          "h-6 w-10 shrink-0 rounded-pill border border-glass p-0.5 transition-colors disabled:opacity-50",
          "focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-neon",
          rule.active ? "bg-focused" : "bg-field",
        )}
      >
        <span
          className={cn(
            "block h-4 w-4 rounded-pill transition-transform",
            rule.active ? "translate-x-4 bg-neon" : "translate-x-0 bg-fg-muted",
          )}
        />
      </button>
      <button
        type="button"
        aria-label={t("settingsAutomation.clone")}
        title={t("settingsAutomation.clone")}
        onClick={(e) => run(() => clone.mutateAsync(rule.id), t("settingsAutomation.cloneFailed"), e)}
        disabled={clone.isPending}
        className="rounded-md p-1.5 text-fg-muted hover:bg-surface-2 hover:text-fg disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Copy className="h-4 w-4" aria-hidden />
      </button>
      <button
        type="button"
        aria-label={t("actions.delete")}
        title={t("actions.delete")}
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          if (!window.confirm(t("settingsAutomation.deleteConfirm", { name: rule.name }))) return;
          run(() => del.mutateAsync(rule.id), t("actions.deleteFailed"));
        }}
        disabled={del.isPending}
        className="rounded-md p-1.5 text-fg-muted hover:bg-surface-2 hover:text-danger disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <Trash2 className="h-4 w-4" aria-hidden />
      </button>
      <ChevronRight className="h-4 w-4 shrink-0 text-fg-muted" aria-hidden />
    </li>
  );
}
