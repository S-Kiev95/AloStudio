"use client";

import Link from "next/link";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useLifecycleReport } from "@/lib/api/lifecycle";
import { useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

/** Estadísticas: contacts per lifecycle stage, and how many entered each
 *  in the period (F17). */
export function LifecycleReportCard({ accountId, days }: { accountId: string; days: number }) {
  const t = useT();
  const report = useLifecycleReport(accountId, days);
  const stages = report.data?.stages ?? [];
  const top = Math.max(1, ...stages.map((s) => s.count));

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("lifecycle.report.title")}</CardTitle>
      </CardHeader>
      <CardContent>
        {report.isLoading ? (
          <p className="py-6 text-center text-sm text-fg-muted">{t("common.loading")}</p>
        ) : report.isError ? (
          <p role="alert" className="py-6 text-center text-sm text-danger">
            {t("lifecycle.report.failed")}
          </p>
        ) : !report.data?.enabled ? (
          <p className="py-6 text-center text-sm text-fg-muted">
            {t("lifecycle.report.off")}{" "}
            <Link
              href={`/accounts/${accountId}/settings/lifecycle`}
              className="text-lit underline-offset-2 hover:underline"
            >
              {t("lifecycle.report.turnOn")}
            </Link>
          </p>
        ) : (
          <ul className="space-y-2">
            {stages.map((s) => (
              <li key={s.key} className="space-y-1">
                <div className="flex items-baseline justify-between gap-3 text-sm">
                  <span className={cn("truncate", s.kind === "lost" ? "text-fg-muted" : "text-fg")}>
                    {s.name}
                  </span>
                  <span className="shrink-0 font-numeric tabular-nums text-fg-muted">
                    {t("lifecycle.report.counts", { count: s.count, entered: s.entered })}
                  </span>
                </div>
                <div className="h-1.5 overflow-hidden rounded-full bg-hover-glass" aria-hidden>
                  <div
                    className={cn("h-full rounded-full", s.kind === "lost" ? "bg-fg-muted" : "bg-neon")}
                    style={{ width: `${s.count ? Math.max((s.count / top) * 100, 2) : 0}%` }}
                  />
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
