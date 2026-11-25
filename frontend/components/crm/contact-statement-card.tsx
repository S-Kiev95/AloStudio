"use client";

import { MessageCircle, Pencil, Plus, Receipt, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useConfirm } from "@/components/ui/confirm-dialog";
import {
  type Payment,
  useContactStatement,
  useDeletePayment,
} from "@/lib/api/crm";
import { useIsAccountAdmin } from "@/lib/api/profile";
import { useIntlTag, useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

import { formatMoney } from "./money";
import { PaymentDialog } from "./payment-dialog";
import { buildReminderText, buildWhatsappReminderHref } from "./reminder";

/** Contact's current account statement card: per-currency balances, overdue
 *  amounts, won sales with what each owes, and payment history. */
export function ContactStatementCard({
  accountId,
  contact,
}: {
  accountId: string;
  contact: { id: number; name: string | null };
}) {
  const t = useT();
  const intlTag = useIntlTag();
  const confirm = useConfirm();
  const isAdmin = useIsAccountAdmin(accountId);
  const { data, isLoading, isError } = useContactStatement(accountId, contact.id);
  const deletePayment = useDeletePayment(accountId);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Payment | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  const hasDebt = (data?.balances ?? []).some((b) => b.owed_total > 0);
  const nextDueOn =
    (data?.balances ?? [])
      .map((b) => b.next_due_on)
      .filter((d): d is string => Boolean(d))
      .sort()[0] ?? null;

  const reminderHref =
    hasDebt && data?.whatsapp_conversation
      ? buildWhatsappReminderHref(
          accountId,
          data.whatsapp_conversation.display_id,
          buildReminderText(t, intlTag, {
            contactName: contact.name,
            currencies: data.balances,
            nextDueOn,
          }),
        )
      : null;

  async function handleDelete(p: Payment) {
    setActionError(null);
    const amountLabel = formatMoney(p.amount, p.currency, intlTag);
    if (!(await confirm(t("collections.payment.deleteConfirm", { amount: amountLabel })))) {
      return;
    }
    try {
      await deletePayment.mutateAsync(p.id);
    } catch (err) {
      setActionError((err as { message?: string })?.message ?? t("actions.deleteFailed"));
    }
  }

  return (
    <Card>
      <CardHeader className="flex flex-row flex-wrap items-center justify-between gap-2">
        <CardTitle className="flex items-center gap-2 text-base">
          <Receipt className="h-4 w-4 text-fg-muted" aria-hidden />
          {t("collections.statement.title")}
        </CardTitle>
        <div className="flex flex-wrap items-center gap-2">
          {hasDebt ? (
            reminderHref ? (
              <Link
                href={reminderHref}
                className="inline-flex h-8 items-center gap-1.5 rounded-md border border-glass bg-surface-2 px-2.5 text-xs font-medium text-fg hover:bg-hover-glass focus-visible:outline focus-visible:outline-2 focus-visible:outline-neon"
              >
                <MessageCircle className="h-3.5 w-3.5 text-success" aria-hidden />
                {t("collections.reminder.button")}
              </Link>
            ) : (
              <Button
                type="button"
                size="sm"
                variant="secondary"
                disabled
                title={t("collections.reminder.noWhatsapp")}
              >
                <MessageCircle className="h-3.5 w-3.5" aria-hidden />
                {t("collections.reminder.button")}
              </Button>
            )
          ) : null}
          <Button size="sm" variant="secondary" onClick={() => setCreating(true)}>
            <Plus className="h-4 w-4" aria-hidden />
            {t("collections.payment.register")}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {actionError ? (
          <p role="alert" className="text-sm text-danger">
            {actionError}
          </p>
        ) : null}

        {isLoading ? (
          <p className="text-sm text-fg-muted">{t("common.loading")}</p>
        ) : isError || !data ? (
          <p role="alert" className="text-sm text-danger">
            {t("collections.statement.loadFailed")}
          </p>
        ) : (
          <>
            {data.balances.length > 0 ? (
              <div className="grid gap-2.5 sm:grid-cols-2">
                {data.balances.map((b) => (
                  <div
                    key={b.currency ?? "__none__"}
                    className={cn(
                      "rounded-md border bg-surface-2 p-3",
                      b.overdue_total > 0 ? "border-danger" : "border-glass",
                    )}
                  >
                    <div className="flex items-center justify-between gap-2 text-xs text-fg-muted">
                      <span>
                        {t("collections.statement.balance")}
                        {b.currency ? ` · ${b.currency}` : ""}
                      </span>
                      {b.overdue_total > 0 ? (
                        <span className="font-medium text-danger">
                          {t("collections.daysOverdue", { days: b.days_overdue })}
                        </span>
                      ) : b.net_balance <= 0 ? (
                        <span className="text-success">{t("collections.statement.settled")}</span>
                      ) : null}
                    </div>
                    <p
                      className={cn(
                        "mt-1 font-numeric text-lg font-semibold tabular-nums",
                        b.overdue_total > 0
                          ? "text-danger"
                          : b.net_balance < 0
                            ? "text-success"
                            : "text-fg",
                      )}
                    >
                      {formatMoney(b.net_balance, b.currency, intlTag)}
                    </p>
                    <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-fg-muted">
                      <span>
                        {t("collections.statement.owed")}:{" "}
                        <strong className="font-numeric tabular-nums text-fg">
                          {formatMoney(b.owed_total, b.currency, intlTag)}
                        </strong>
                      </span>
                      {b.overdue_total > 0 ? (
                        <span className="text-danger">
                          {t("collections.statement.overdue")}:{" "}
                          <strong className="font-numeric tabular-nums">
                            {formatMoney(b.overdue_total, b.currency, intlTag)}
                          </strong>
                        </span>
                      ) : null}
                      {b.credit_balance > 0 ? (
                        <span className="text-success">
                          {t("collections.statement.credit")}:{" "}
                          <strong className="font-numeric tabular-nums">
                            {formatMoney(b.credit_balance, b.currency, intlTag)}
                          </strong>
                        </span>
                      ) : null}
                    </div>
                  </div>
                ))}
              </div>
            ) : null}

            <div className="space-y-2">
              <h3 className="text-xs font-medium uppercase tracking-wide text-fg-muted">
                {t("collections.statement.sales")}
              </h3>
              {data.sales.length === 0 ? (
                <p className="text-sm text-fg-muted">{t("collections.statement.noSales")}</p>
              ) : (
                <ul className="divide-y divide-glass">
                  {data.sales.map((s) => (
                    <li key={s.id} className="space-y-1 py-2">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-fg">{s.title}</p>
                          <p className="text-xs text-fg-muted">
                            {s.payment_terms
                              ? t(`collections.billing.${s.payment_terms}`)
                              : t("collections.billing.unset")}
                            {s.next_due_on ? ` · ${t("collections.billing.dueOn")} ${s.next_due_on}` : ""}
                            {s.days_overdue > 0 ? (
                              <span className="ml-1.5 font-medium text-danger">
                                · {t("collections.daysOverdue", { days: s.days_overdue })}
                              </span>
                            ) : null}
                          </p>
                        </div>
                        <div className="shrink-0 text-right font-numeric text-xs tabular-nums">
                          <p className="text-fg">
                            {s.value != null ? formatMoney(s.value, s.currency, intlTag) : "—"}
                          </p>
                          {s.owed_amount > 0 ? (
                            <p className={cn(s.overdue_amount > 0 ? "font-medium text-danger" : "text-fg-muted")}>
                              {t("collections.payment.saleOwed", {
                                amount: formatMoney(s.owed_amount, s.currency, intlTag),
                              })}
                            </p>
                          ) : (
                            <p className="text-success">{t("collections.billing.settled")}</p>
                          )}
                        </div>
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="space-y-2">
              <h3 className="text-xs font-medium uppercase tracking-wide text-fg-muted">
                {t("collections.statement.payments")}
              </h3>
              {data.payments.length === 0 ? (
                <p className="text-sm text-fg-muted">{t("collections.statement.noPayments")}</p>
              ) : (
                <ul className="divide-y divide-glass">
                  {data.payments.map((p) => (
                    <li key={p.id} className="flex items-start justify-between gap-3 py-2">
                      <div className="min-w-0 text-xs">
                        <p className="font-medium text-fg">
                          <span className="font-numeric tabular-nums">
                            {formatMoney(p.amount, p.currency, intlTag)}
                          </span>
                          <span className="ml-2 font-normal text-fg-muted">
                            {p.paid_on} · {t(`collections.payment.methods.${p.method}`)}
                          </span>
                        </p>
                        {p.allocations.length > 0 ? (
                          <p className="truncate text-fg-muted">
                            {p.allocations
                              .map(
                                (a) =>
                                  `${a.opportunity_title ?? `#${a.opportunity_id}`}${a.installment_number ? ` (#${a.installment_number})` : ""}: ${formatMoney(a.amount, p.currency, intlTag)}`,
                              )
                              .join(" · ")}
                          </p>
                        ) : null}
                        {p.unallocated_amount > 0 ? (
                          <p className="text-success">
                            {t("collections.payment.creditTag", {
                              amount: formatMoney(p.unallocated_amount, p.currency, intlTag),
                            })}
                          </p>
                        ) : null}
                        {p.note ? <p className="text-fg-muted">{p.note}</p> : null}
                        {p.created_by ? (
                          <p className="text-fg-muted">
                            {t("collections.payment.registeredBy", { name: p.created_by.name })}
                          </p>
                        ) : null}
                      </div>
                      <div className="flex shrink-0 items-center gap-1">
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          aria-label={t("collections.payment.edit")}
                          onClick={() => setEditing(p)}
                        >
                          <Pencil className="h-3.5 w-3.5" aria-hidden />
                        </Button>
                        {isAdmin ? (
                          <Button
                            type="button"
                            size="sm"
                            variant="ghost"
                            aria-label={t("actions.delete")}
                            onClick={() => void handleDelete(p)}
                            disabled={deletePayment.isPending}
                          >
                            <Trash2 className="h-3.5 w-3.5 text-danger" aria-hidden />
                          </Button>
                        ) : null}
                      </div>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </>
        )}
      </CardContent>

      <PaymentDialog
        accountId={accountId}
        contactId={contact.id}
        contactName={contact.name}
        open={creating || editing !== null}
        initial={editing}
        onClose={() => {
          setCreating(false);
          setEditing(null);
        }}
      />
    </Card>
  );
}
