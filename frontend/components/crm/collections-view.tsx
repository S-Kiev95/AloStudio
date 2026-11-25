"use client";

import { AlertTriangle, Banknote, CheckCircle2, MessageCircle, Search } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { PageHeader } from "@/components/shell/page-header";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ErrorState } from "@/components/ui/error-state";
import { Input } from "@/components/ui/input";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { selectClassName } from "@/components/ui/select";
import { useAgents } from "@/lib/api/account";
import {
  type ReceivableRow,
  useReceivables,
  useReceivablesSummary,
} from "@/lib/api/crm";
import { useIntlTag, useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

import { formatMoney } from "./money";
import { PaymentDialog } from "./payment-dialog";
import { buildReminderText, buildWhatsappReminderHref } from "./reminder";

type StatusFilter = "all" | "overdue" | "upcoming";
type SortField = "overdue" | "amount" | "due_on" | "name";

/** CRM Collections tab: summary KPIs by currency, filterable accounts
 *  receivable table, quick payment registration, and WhatsApp reminder link. */
export function CollectionsView({ accountId }: { accountId: string }) {
  const t = useT();
  const intlTag = useIntlTag();
  const [status, setStatus] = useState<StatusFilter>("all");
  const [ownerId, setOwnerId] = useState<string>("");
  const [sort, setSort] = useState<SortField>("overdue");
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [payingRow, setPayingRow] = useState<ReceivableRow | null>(null);

  const agents = useAgents(accountId);
  const summary = useReceivablesSummary(accountId);
  const receivables = useReceivables(accountId, {
    status,
    owner_id: ownerId ? Number(ownerId) : undefined,
    q: query.trim() || undefined,
    sort,
    order: sort === "name" || sort === "due_on" ? "asc" : "desc",
    page,
    per_page: 25,
  });

  const summaryCurrencies = summary.data?.currencies ?? [];
  const toCollectList = summaryCurrencies.filter((c) => c.to_collect > 0);
  const overdueList = summaryCurrencies.filter((c) => c.overdue > 0);
  const collectedList = summaryCurrencies.filter((c) => c.collected_this_month > 0);

  return (
    <div className="space-y-4">
      <PageHeader title={t("collections.pageTitle")} description={t("collections.subtitle")} />

      {/* Top KPI summary cards (never mixing/converting currencies) */}
      <div className="grid gap-3 sm:grid-cols-3">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between text-xs text-fg-muted">
              <span>{t("collections.summary.toCollect")}</span>
              <Banknote className="h-4 w-4 text-fg-muted" aria-hidden />
            </div>
            <div className="mt-1.5 space-y-0.5">
              {toCollectList.length === 0 ? (
                <p className="font-numeric text-lg font-semibold text-fg-muted">
                  {t("collections.summary.none")}
                </p>
              ) : (
                toCollectList.map((c) => (
                  <p
                    key={c.currency ?? "__none__"}
                    className="font-numeric text-xl font-semibold tabular-nums text-fg"
                  >
                    {formatMoney(c.to_collect, c.currency, intlTag)}
                  </p>
                ))
              )}
            </div>
            {summary.data ? (
              <p className="mt-1 text-xs text-fg-muted">
                {t("collections.summary.debtorsCount", { count: summary.data.debtors_count })}
              </p>
            ) : null}
          </CardContent>
        </Card>

        <Card className={cn(overdueList.length > 0 && "border-danger")}>
          <CardContent className="p-4">
            <div className="flex items-center justify-between text-xs text-fg-muted">
              <span>{t("collections.summary.overdue")}</span>
              <AlertTriangle
                className={cn("h-4 w-4", overdueList.length > 0 ? "text-danger" : "text-fg-muted")}
                aria-hidden
              />
            </div>
            <div className="mt-1.5 space-y-0.5">
              {overdueList.length === 0 ? (
                <p className="font-numeric text-lg font-semibold text-fg-muted">
                  {t("collections.summary.none")}
                </p>
              ) : (
                overdueList.map((c) => (
                  <p
                    key={c.currency ?? "__none__"}
                    className="font-numeric text-xl font-semibold tabular-nums text-danger"
                  >
                    {formatMoney(c.overdue, c.currency, intlTag)}
                  </p>
                ))
              )}
            </div>
            {summary.data ? (
              <p className={cn("mt-1 text-xs", overdueList.length > 0 ? "text-danger" : "text-fg-muted")}>
                {t("collections.summary.overdueCount", { count: summary.data.overdue_debtors_count })}
              </p>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between text-xs text-fg-muted">
              <span>{t("collections.summary.collectedThisMonth")}</span>
              <CheckCircle2 className="h-4 w-4 text-success" aria-hidden />
            </div>
            <div className="mt-1.5 space-y-0.5">
              {collectedList.length === 0 ? (
                <p className="font-numeric text-lg font-semibold text-fg-muted">
                  {t("collections.summary.none")}
                </p>
              ) : (
                collectedList.map((c) => (
                  <p
                    key={c.currency ?? "__none__"}
                    className="font-numeric text-xl font-semibold tabular-nums text-success"
                  >
                    {formatMoney(c.collected_this_month, c.currency, intlTag)}
                  </p>
                ))
              )}
            </div>
            {summary.data ? (
              <p className="mt-1 font-numeric text-xs tabular-nums text-fg-muted">
                {summary.data.month}
              </p>
            ) : null}
          </CardContent>
        </Card>
      </div>

      {/* Filters bar */}
      <div className="flex flex-wrap items-center gap-3">
        <SegmentedControl
          ariaLabel={t("collections.filters.status")}
          size="sm"
          value={status}
          onValueChange={(v) => {
            setStatus(v);
            setPage(1);
          }}
          options={[
            { value: "all", label: t("collections.filters.all") },
            { value: "overdue", label: t("collections.filters.overdue") },
            { value: "upcoming", label: t("collections.filters.upcoming") },
          ]}
        />

        <select
          aria-label={t("collections.filters.owner")}
          value={ownerId}
          onChange={(e) => {
            setOwnerId(e.target.value);
            setPage(1);
          }}
          className={cn(selectClassName("sm"), "w-auto")}
        >
          <option value="">{t("collections.filters.allOwners")}</option>
          {(agents.data ?? []).map((a) => (
            <option key={a.id} value={String(a.id)}>
              {a.available_name || a.name}
            </option>
          ))}
        </select>

        <select
          aria-label={t("collections.filters.sort")}
          value={sort}
          onChange={(e) => {
            setSort(e.target.value as SortField);
            setPage(1);
          }}
          className={cn(selectClassName("sm"), "w-auto")}
        >
          <option value="overdue">{t("collections.sort.overdue")}</option>
          <option value="amount">{t("collections.sort.amount")}</option>
          <option value="due_on">{t("collections.sort.dueOn")}</option>
          <option value="name">{t("collections.sort.name")}</option>
        </select>

        <div className="relative w-64 max-w-full">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-muted"
            aria-hidden
          />
          <Input
            aria-label={t("collections.filters.search")}
            placeholder={t("collections.filters.search")}
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setPage(1);
            }}
            className="h-9 pl-9"
          />
        </div>
      </div>

      {/* Table */}
      {receivables.isLoading ? (
        <div aria-busy="true" className="space-y-2">
          <span className="sr-only">{t("common.loading")}</span>
          {Array.from({ length: 4 }).map((_, i) => (
            <div key={i} aria-hidden className="h-14 animate-pulse rounded-md bg-surface-2" />
          ))}
        </div>
      ) : receivables.isError || !receivables.data ? (
        <ErrorState
          message={t("collections.loadFailed")}
          onRetry={() => {
            void receivables.refetch();
            void summary.refetch();
          }}
          retrying={receivables.isFetching}
        />
      ) : receivables.data.items.length === 0 ? (
        <Card>
          <CardContent className="p-8 text-center text-sm text-fg-muted">
            {t("collections.noDebtors")}
          </CardContent>
        </Card>
      ) : (
        <Card>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="border-b border-glass text-xs text-fg-muted">
                <tr>
                  <th className="px-4 py-3 font-medium">{t("collections.table.client")}</th>
                  <th className="px-4 py-3 font-medium">{t("collections.table.owed")}</th>
                  <th className="px-4 py-3 font-medium">{t("collections.table.overdue")}</th>
                  <th className="px-4 py-3 font-medium">{t("collections.table.due")}</th>
                  <th className="px-4 py-3 font-medium">{t("collections.table.owner")}</th>
                  <th className="px-4 py-3 text-right font-medium">
                    {t("collections.table.actions")}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y divide-glass">
                {receivables.data.items.map((row) => {
                  const name =
                    row.contact.name?.trim() ||
                    row.contact.phone_number ||
                    row.contact.email ||
                    t("conversations.contact.fallbackName", { id: row.contact.id });
                  const reminderHref = row.whatsapp_conversation
                    ? buildWhatsappReminderHref(
                        accountId,
                        row.whatsapp_conversation.display_id,
                        buildReminderText(t, intlTag, {
                          contactName: row.contact.name,
                          currencies: row.currencies,
                          nextDueOn: row.next_due_on,
                        }),
                      )
                    : null;
                  return (
                    <tr key={row.contact.id} className="hover:bg-hover-glass">
                      <td className="px-4 py-3">
                        <Link
                          href={`/accounts/${accountId}/contacts/${row.contact.id}`}
                          className="flex items-center gap-2.5 focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon"
                        >
                          <Avatar name={name} src={row.contact.avatar_url} size="sm" />
                          <div className="min-w-0">
                            <p className="truncate font-medium text-fg hover:underline">{name}</p>
                            <p className="text-xs text-fg-muted">
                              {t("collections.salesCount", { count: row.sales_count })}
                            </p>
                          </div>
                        </Link>
                      </td>
                      <td className="px-4 py-3 font-numeric tabular-nums">
                        {row.currencies.map((c) => (
                          <div key={c.currency ?? "__none__"}>
                            <span className="font-medium text-fg">
                              {formatMoney(c.owed_total, c.currency, intlTag)}
                            </span>
                            {c.credit_balance > 0 ? (
                              <span className="ml-1.5 text-xs text-success">
                                ({t("collections.payment.creditTag", {
                                  amount: formatMoney(c.credit_balance, c.currency, intlTag),
                                })})
                              </span>
                            ) : null}
                          </div>
                        ))}
                      </td>
                      <td className="px-4 py-3 font-numeric tabular-nums">
                        {row.days_overdue > 0 ? (
                          <div>
                            {row.currencies
                              .filter((c) => c.overdue_total > 0)
                              .map((c) => (
                                <p key={c.currency ?? "__none__"} className="font-medium text-danger">
                                  {formatMoney(c.overdue_total, c.currency, intlTag)}
                                </p>
                              ))}
                            <span className="text-xs text-danger">
                              {t("collections.daysOverdue", { days: row.days_overdue })}
                            </span>
                          </div>
                        ) : (
                          <span className="text-fg-muted">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 font-numeric tabular-nums text-xs">
                        {row.next_due_on ? (
                          <span className={cn(row.days_overdue > 0 ? "font-medium text-danger" : "text-fg-muted")}>
                            {new Date(`${row.next_due_on}T00:00:00`).toLocaleDateString(intlTag, {
                              day: "numeric",
                              month: "short",
                              year: "numeric",
                            })}
                          </span>
                        ) : (
                          <span className="text-fg-muted">—</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-xs text-fg-muted">
                        {row.owner?.name ?? "—"}
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-1.5">
                          <Button
                            type="button"
                            size="sm"
                            variant="secondary"
                            onClick={() => setPayingRow(row)}
                          >
                            {t("collections.payment.register")}
                          </Button>
                          {reminderHref ? (
                            <Link
                              href={reminderHref}
                              aria-label={`${t("collections.reminder.button")}: ${name}`}
                              title={t("collections.reminder.button")}
                              className="inline-flex h-8 items-center gap-1 rounded-md border border-glass bg-surface-2 px-2.5 text-xs font-medium text-fg hover:bg-hover-glass focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon"
                            >
                              <MessageCircle className="h-3.5 w-3.5 text-success" aria-hidden />
                              <span className="hidden xl:inline">
                                {t("collections.reminder.button")}
                              </span>
                            </Link>
                          ) : (
                            <Button
                              type="button"
                              size="sm"
                              variant="ghost"
                              disabled
                              aria-label={`${t("collections.reminder.button")}: ${name}`}
                              title={t("collections.reminder.noWhatsapp")}
                            >
                              <MessageCircle className="h-3.5 w-3.5" aria-hidden />
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {receivables.data.meta.total_pages > 1 ? (
            <div className="flex items-center justify-between border-t border-glass px-4 py-3 text-xs text-fg-muted">
              <span>
                {t("collections.pageOf", {
                  page: receivables.data.meta.page,
                  total: receivables.data.meta.total_pages,
                })}
              </span>
              <div className="flex gap-2">
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  {t("collections.prevPage")}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  disabled={page >= receivables.data.meta.total_pages}
                  onClick={() => setPage((p) => p + 1)}
                >
                  {t("collections.nextPage")}
                </Button>
              </div>
            </div>
          ) : null}
        </Card>
      )}

      {payingRow ? (
        <PaymentDialog
          accountId={accountId}
          contactId={payingRow.contact.id}
          contactName={payingRow.contact.name}
          open={true}
          onClose={() => setPayingRow(null)}
          defaultCurrency={payingRow.currencies[0]?.currency ?? null}
        />
      ) : null}
    </div>
  );
}
