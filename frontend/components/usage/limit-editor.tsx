"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  type UsageLimit,
  type UsageLimitKind,
  useSetUsageLimit,
} from "@/lib/api/usage";
import { useIntlTag, useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

/** The monthly spend cap of one kind: how much of it went, and the field
 *  to set, change or remove it (F6). */
export function LimitEditor({
  accountId,
  kind,
  limit,
  currency,
}: {
  accountId: string;
  kind: UsageLimitKind;
  limit: UsageLimit | undefined;
  currency: string;
}) {
  const t = useT();
  const tag = useIntlTag();
  const save = useSetUsageLimit(accountId);
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const money = (n: number) =>
    new Intl.NumberFormat(tag, { style: "currency", currency, maximumFractionDigits: 2 }).format(n);

  async function submit(next: number | null) {
    setError(null);
    if (next !== null && (!Number.isFinite(next) || next < 0)) {
      setError(t("usage.limitInvalid"));
      return;
    }
    try {
      await save.mutateAsync({ kind, monthlyLimit: next });
      setEditing(false);
    } catch {
      setError(t("usage.limitFailed"));
    }
  }

  const cap = limit?.monthly_limit ?? null;
  const percent = Math.min(limit?.percent ?? 0, 100);
  const hint = kind === "whatsapp" ? t("usage.limitHintWhatsapp") : t("usage.limitHintAi");

  return (
    <div
      className="space-y-2 rounded-lg border border-glass bg-surface-2 p-3"
      data-testid={`limit-${kind}`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm font-semibold text-fg">{t("usage.limitTitle")}</span>
        {editing ? (
          <form
            className="flex flex-wrap items-center gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              void submit(Number(value.replace(",", ".")));
            }}
          >
            <Input
              aria-label={t("usage.limitTitle")}
              inputMode="decimal"
              className="h-9 w-28"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              autoFocus
            />
            <span className="text-xs text-fg-muted">{currency}</span>
            <Button type="submit" size="sm" loading={save.isPending}>
              {t("usage.limitSave")}
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={() => setEditing(false)}>
              {t("usage.limitCancel")}
            </Button>
          </form>
        ) : (
          <div className="flex items-center gap-2">
            <span className="text-sm text-fg-muted">
              {cap === null
                ? t("usage.limitNone")
                : t("usage.limitOf", {
                    spent: money(limit?.spent ?? 0),
                    limit: money(cap),
                    percent: String(limit?.percent ?? 0),
                  })}
            </span>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => {
                setValue(cap === null ? "" : String(cap));
                setEditing(true);
              }}
            >
              {cap === null ? t("usage.limitSet") : t("usage.limitEdit")}
            </Button>
            {cap !== null ? (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                loading={save.isPending}
                onClick={() => void submit(null)}
              >
                {t("usage.limitRemove")}
              </Button>
            ) : null}
          </div>
        )}
      </div>
      {cap !== null ? (
        <div
          className="h-2 overflow-hidden rounded-pill bg-field"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={percent}
        >
          <div
            className={cn(
              "h-full rounded-pill",
              limit?.reached ? "bg-danger" : percent >= 80 ? "bg-warning" : "bg-success",
            )}
            style={{ width: `${percent}%` }}
          />
        </div>
      ) : null}
      {limit?.reached ? (
        <p role="alert" className="text-xs text-danger">
          {kind === "whatsapp" ? t("usage.limitReachedWhatsapp") : t("usage.limitReachedAi")}
        </p>
      ) : (
        <p className="text-xs text-fg-muted">{hint}</p>
      )}
      {error ? (
        <p role="alert" className="text-xs text-danger">
          {error}
        </p>
      ) : null}
    </div>
  );
}
