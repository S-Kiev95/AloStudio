"use client";

import Link from "next/link";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useClosingReport, useClosingSettings } from "@/lib/api/closing";
import { useIntlTag, useT } from "@/lib/i18n/provider";

/** Estadísticas: how many conversations closed for each reason (F17). */
export function ClosingReportCard({ accountId, days }: { accountId: string; days: number }) {
  const t = useT();
  const tag = useIntlTag();
  const settings = useClosingSettings(accountId);
  const report = useClosingReport(accountId, days);
  const percent = new Intl.NumberFormat(tag, { style: "percent", maximumFractionDigits: 0 });
  const total = report.data?.total ?? 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("closing.report.title")}</CardTitle>
      </CardHeader>
      <CardContent>
        {report.isLoading ? (
          <p className="py-6 text-center text-sm text-fg-muted">{t("common.loading")}</p>
        ) : report.isError ? (
          <p role="alert" className="py-6 text-center text-sm text-danger">
            {t("closing.report.failed")}
          </p>
        ) : total === 0 ? (
          <p className="py-6 text-center text-sm text-fg-muted">
            {settings.data && !settings.data.enabled ? (
              <>
                {t("closing.report.off")}{" "}
                <Link
                  href={`/accounts/${accountId}/settings/closing_notes`}
                  className="text-lit underline-offset-2 hover:underline"
                >
                  {t("closing.report.turnOn")}
                </Link>
              </>
            ) : (
              t("closing.report.empty")
            )}
          </p>
        ) : (
          <div className="space-y-3">
            <p className="text-sm text-fg-muted">
              {t("closing.report.total", { count: total })}
            </p>
            <ul className="space-y-2">
              {report.data?.categories.map((row) => {
                const share = row.count / total;
                const name = row.category ?? t("closing.report.none");
                return (
                  <li key={row.category ?? "—"} className="space-y-1">
                    <div className="flex items-baseline justify-between gap-3 text-sm">
                      <span className="truncate text-fg">{name}</span>
                      <span className="shrink-0 font-numeric tabular-nums text-fg-muted">
                        {row.count} · {percent.format(share)}
                      </span>
                    </div>
                    <div className="h-1.5 overflow-hidden rounded-full bg-hover-glass" aria-hidden>
                      <div
                        className="h-full rounded-full bg-neon"
                        style={{ width: `${Math.max(share * 100, 2)}%` }}
                      />
                    </div>
                  </li>
                );
              })}
            </ul>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
