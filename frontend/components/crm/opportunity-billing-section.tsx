"use client";

import { Banknote, Lock } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { selectClassName } from "@/components/ui/select";
import {
  type Opportunity,
  type OpportunityBillingInput,
  type PaymentMethod,
  type PaymentTerms,
  useOpportunityBilling,
  useSaveOpportunityBilling,
} from "@/lib/api/crm";
import { useIntlTag, useT } from "@/lib/i18n/provider";
import { cn } from "@/lib/utils";

import { formatMoney } from "./money";
import { PaymentDialog } from "./payment-dialog";

type DraftInstallment = {
  id?: number;
  number: number;
  due_on: string;
  amount: string;
  locked: boolean;
  status?: "paid" | "partial" | "pending" | "overdue";
  paid_amount?: number;
};

function todayIso(): string {
  return new Date().toISOString().slice(0, 10);
}

/** Billing section embedded inside OpportunityDialog for won opportunities. */
export function OpportunityBillingSection({
  accountId,
  opportunity,
}: {
  accountId: string;
  opportunity: Opportunity;
}) {
  const t = useT();
  const intlTag = useIntlTag();
  const billingQ = useOpportunityBilling(accountId, opportunity.id, true);
  const saveBilling = useSaveOpportunityBilling(accountId, opportunity.id);

  const [terms, setTerms] = useState<PaymentTerms | "">("");
  const [dueOn, setDueOn] = useState("");
  const [registerNow, setRegisterNow] = useState(true);
  const [cashMethod, setCashMethod] = useState<PaymentMethod>("cash");
  const [cashPaidOn, setCashPaidOn] = useState(todayIso);

  const [genCount, setGenCount] = useState("3");
  const [genFirstDue, setGenFirstDue] = useState(todayIso);
  const [genFreq, setGenFreq] = useState<"monthly" | "every_n_days">("monthly");
  const [genInterval, setGenInterval] = useState("30");
  const [draftInsts, setDraftInsts] = useState<DraftInstallment[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [payOpen, setPayOpen] = useState(false);

  const billing = billingQ.data;
  const anyLocked = (billing?.installments ?? []).some((i) => i.locked);

  useEffect(() => {
    if (!billing) return;
    setTerms(billing.payment_terms ?? "");
    setDueOn(billing.due_on ?? "");
    setRegisterNow(billing.owed_amount > 0 && billing.payment_terms !== "cash");
    setDraftInsts(
      billing.installments.map((i) => ({
        id: i.id,
        number: i.number,
        due_on: i.due_on,
        amount: String(i.amount),
        locked: i.locked,
        status: i.status,
        paid_amount: i.paid_amount,
      })),
    );
  }, [billing]);

  async function handleGenerateInstallments() {
    setError(null);
    const count = Number(genCount);
    const interval = Number(genInterval);
    try {
      await saveBilling.mutateAsync({
        payment_terms: "installments",
        generate: {
          count,
          first_due_on: genFirstDue,
          frequency: genFreq,
          interval_days: genFreq === "every_n_days" ? interval : null,
        },
      });
    } catch (err) {
      setError((err as { message?: string })?.message ?? t("collections.billing.saveFailed"));
    }
  }

  async function handleSaveBilling() {
    setError(null);
    const payload: OpportunityBillingInput = {
      payment_terms: terms || null,
    };
    if (terms === "cash") {
      const canAutoPay =
        registerNow &&
        Boolean(opportunity.contact_id) &&
        (billing?.owed_amount ?? opportunity.value ?? 0) > 0;
      payload.register_payment = canAutoPay;
      if (canAutoPay) {
        payload.payment_method = cashMethod;
        payload.paid_on = cashPaidOn;
      }
    } else if (terms === "credit") {
      payload.due_on = dueOn || null;
    } else if (terms === "installments") {
      if (draftInsts.length > 0 && !anyLocked) {
        payload.installments = draftInsts.map((i) => ({
          id: i.id,
          due_on: i.due_on,
          amount: Number(i.amount.replace(",", ".")),
        }));
      } else if (draftInsts.length === 0) {
        payload.generate = {
          count: Number(genCount),
          first_due_on: genFirstDue,
          frequency: genFreq,
          interval_days: genFreq === "every_n_days" ? Number(genInterval) : null,
        };
      }
    }
    try {
      await saveBilling.mutateAsync(payload);
    } catch (err) {
      setError((err as { message?: string })?.message ?? t("collections.billing.saveFailed"));
    }
  }

  return (
    <section
      aria-label={t("collections.billing.sectionTitle")}
      className="space-y-3 rounded-md border border-glass bg-surface-2 p-3.5"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="flex items-center gap-1.5 text-sm font-medium text-fg">
          <Banknote className="h-4 w-4 text-fg-muted" aria-hidden />
          {t("collections.billing.sectionTitle")}
        </h3>
        {opportunity.contact_id ? (
          <Button
            type="button"
            size="sm"
            variant="secondary"
            onClick={() => setPayOpen(true)}
            disabled={billingQ.isLoading}
          >
            {t("collections.payment.register")}
          </Button>
        ) : (
          <span className="text-xs text-fg-muted">
            {t("collections.billing.needContactForPayment")}
          </span>
        )}
      </div>

      {billing ? (
        <div className="grid grid-cols-3 gap-2 rounded-md border border-glass bg-surface p-2.5 text-xs">
          <div>
            <span className="block text-fg-muted">{t("collections.billing.paid")}</span>
            <span className="font-numeric font-medium tabular-nums text-success">
              {formatMoney(billing.paid_amount, billing.currency, intlTag)}
            </span>
          </div>
          <div>
            <span className="block text-fg-muted">{t("collections.billing.owed")}</span>
            <span className="font-numeric font-medium tabular-nums text-fg">
              {formatMoney(billing.owed_amount, billing.currency, intlTag)}
            </span>
          </div>
          <div>
            <span className="block text-fg-muted">{t("collections.billing.overdue")}</span>
            <span
              className={cn(
                "font-numeric font-medium tabular-nums",
                billing.overdue_amount > 0 ? "text-danger" : "text-fg-muted",
              )}
            >
              {formatMoney(billing.overdue_amount, billing.currency, intlTag)}
            </span>
          </div>
        </div>
      ) : null}

      {error ? (
        <p role="alert" className="text-xs text-danger">
          {error}
        </p>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1">
          <Label htmlFor="billing-terms">{t("collections.billing.terms")}</Label>
          <select
            id="billing-terms"
            value={terms}
            disabled={anyLocked}
            onChange={(e) => setTerms(e.target.value as PaymentTerms | "")}
            className={selectClassName("sm")}
          >
            <option value="">{t("collections.billing.unset")}</option>
            <option value="cash">{t("collections.billing.cash")}</option>
            <option value="credit">{t("collections.billing.credit")}</option>
            <option value="installments">{t("collections.billing.installments")}</option>
          </select>
        </div>

        {terms === "credit" ? (
          <div className="space-y-1">
            <Label htmlFor="billing-due-on">{t("collections.billing.dueOn")}</Label>
            <Input
              id="billing-due-on"
              type="date"
              value={dueOn}
              onChange={(e) => setDueOn(e.target.value)}
              className="h-9 tabular-nums"
            />
          </div>
        ) : null}
      </div>

      {terms === "cash" &&
      opportunity.contact_id &&
      (billing?.owed_amount ?? opportunity.value ?? 0) > 0 ? (
        <div className="space-y-2 rounded-md border border-glass bg-surface p-2.5 text-xs">
          <label className="flex items-center gap-2 font-medium text-fg">
            <input
              type="checkbox"
              checked={registerNow}
              onChange={(e) => setRegisterNow(e.target.checked)}
            />
            {t("collections.billing.registerNow")}
          </label>
          {registerNow ? (
            <div className="grid gap-2 sm:grid-cols-2">
              <select
                aria-label={t("collections.payment.method")}
                value={cashMethod}
                onChange={(e) => setCashMethod(e.target.value as PaymentMethod)}
                className={selectClassName("sm")}
              >
                {(["cash", "transfer", "card", "other"] as const).map((m) => (
                  <option key={m} value={m}>
                    {t(`collections.payment.methods.${m}`)}
                  </option>
                ))}
              </select>
              <Input
                aria-label={t("collections.payment.paidOn")}
                type="date"
                value={cashPaidOn}
                onChange={(e) => setCashPaidOn(e.target.value)}
                className="h-9 tabular-nums"
              />
            </div>
          ) : null}
        </div>
      ) : null}

      {terms === "installments" ? (
        <div className="space-y-2.5">
          {!anyLocked ? (
            <div className="grid gap-2 rounded-md border border-glass bg-surface p-2.5 sm:grid-cols-2">
              <div className="space-y-1">
                <Label htmlFor="inst-count">{t("collections.billing.count")}</Label>
                <Input
                  id="inst-count"
                  type="number"
                  min={1}
                  max={120}
                  value={genCount}
                  onChange={(e) => setGenCount(e.target.value)}
                  className="h-8 tabular-nums"
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="inst-first">{t("collections.billing.firstDueOn")}</Label>
                <Input
                  id="inst-first"
                  type="date"
                  value={genFirstDue}
                  onChange={(e) => setGenFirstDue(e.target.value)}
                  className="h-8 tabular-nums"
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="inst-freq">{t("collections.billing.frequency")}</Label>
                <select
                  id="inst-freq"
                  value={genFreq}
                  onChange={(e) => setGenFreq(e.target.value as "monthly" | "every_n_days")}
                  className={selectClassName("sm")}
                >
                  <option value="monthly">{t("collections.billing.monthly")}</option>
                  <option value="every_n_days">{t("collections.billing.everyNDays")}</option>
                </select>
              </div>
              {genFreq === "every_n_days" ? (
                <div className="space-y-1">
                  <Label htmlFor="inst-interval">{t("collections.billing.intervalDays")}</Label>
                  <Input
                    id="inst-interval"
                    type="number"
                    min={1}
                    max={365}
                    value={genInterval}
                    onChange={(e) => setGenInterval(e.target.value)}
                    className="h-8 tabular-nums"
                  />
                </div>
              ) : null}
              <div className="flex items-end sm:col-span-2">
                <Button
                  type="button"
                  size="sm"
                  variant="secondary"
                  loading={saveBilling.isPending}
                  onClick={() => void handleGenerateInstallments()}
                >
                  {t("collections.billing.generate")}
                </Button>
              </div>
            </div>
          ) : (
            <p className="flex items-center gap-1.5 text-xs text-fg-muted">
              <Lock className="h-3.5 w-3.5" aria-hidden />
              {t("collections.billing.installmentsLockedHint")}
            </p>
          )}

          {draftInsts.length > 0 ? (
            <ul className="space-y-1.5">
              {draftInsts.map((inst, idx) => (
                <li
                  key={inst.id ?? idx}
                  className="grid grid-cols-[auto_1fr_7rem_auto] items-center gap-2 rounded-md border border-glass bg-surface px-2 py-1.5 text-xs"
                >
                  <span className="font-medium text-fg-muted">#{inst.number}</span>
                  <Input
                    type="date"
                    aria-label={`${t("collections.billing.installmentNumber", { n: inst.number })} ${t("collections.billing.dueOn")}`}
                    value={inst.due_on}
                    disabled={anyLocked}
                    onChange={(e) =>
                      setDraftInsts((prev) =>
                        prev.map((row, i) => (i === idx ? { ...row, due_on: e.target.value } : row)),
                      )
                    }
                    className="h-7 tabular-nums text-xs"
                  />
                  <Input
                    inputMode="decimal"
                    aria-label={`${t("collections.billing.installmentNumber", { n: inst.number })} ${t("collections.payment.amount")}`}
                    value={inst.amount}
                    disabled={anyLocked}
                    onChange={(e) =>
                      setDraftInsts((prev) =>
                        prev.map((row, i) => (i === idx ? { ...row, amount: e.target.value } : row)),
                      )
                    }
                    className="h-7 text-right tabular-nums text-xs"
                  />
                  {inst.status ? (
                    <span
                      className={cn(
                        "rounded-pill border px-2 py-0.5 text-[11px] font-medium",
                        inst.status === "overdue"
                          ? "border-danger text-danger"
                          : inst.status === "paid"
                            ? "border-success text-success"
                            : "border-glass text-fg-muted",
                      )}
                    >
                      {t(`collections.billing.status.${inst.status}`)}
                    </span>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      ) : null}

      {!anyLocked ? (
        <div className="flex justify-end">
          <Button
            type="button"
            size="sm"
            variant="secondary"
            loading={saveBilling.isPending}
            onClick={() => void handleSaveBilling()}
          >
            {t("collections.billing.saveTerms")}
          </Button>
        </div>
      ) : null}

      {billing && billing.allocations.length > 0 ? (
        <div className="space-y-1 border-t border-glass pt-2">
          <p className="text-xs font-medium text-fg-muted">
            {t("collections.statement.payments")}
          </p>
          <ul className="space-y-1 text-xs">
            {billing.allocations.map((a) => (
              <li key={a.id} className="flex items-center justify-between gap-2 text-fg">
                <span className="truncate text-fg-muted">
                  {a.paid_on ?? ""}
                  {a.method ? ` · ${t(`collections.payment.methods.${a.method}`)}` : ""}
                  {a.installment_number
                    ? ` · ${t("collections.billing.installmentNumber", { n: a.installment_number })}`
                    : ""}
                </span>
                <span className="shrink-0 font-numeric tabular-nums font-medium">
                  {formatMoney(a.amount, billing.currency, intlTag)}
                </span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {opportunity.contact_id ? (
        <PaymentDialog
          accountId={accountId}
          contactId={opportunity.contact_id}
          contactName={opportunity.contact?.name}
          open={payOpen}
          onClose={() => setPayOpen(false)}
          defaultCurrency={opportunity.currency}
          defaultOpportunityId={opportunity.id}
          defaultAmount={billing?.owed_amount ?? opportunity.value}
        />
      ) : null}
    </section>
  );
}
